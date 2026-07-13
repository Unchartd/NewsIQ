"""Celery background tasks for ingestion, embedding, event extraction, and clustering.

Architecture note — Celery prefork + asyncpg + Python 3.12:
  Celery uses the prefork pool (fork-based). Each worker child inherits the
  parent's SQLAlchemy async engine whose asyncpg connections are bound to the
  parent's event loop. Reusing them in a forked child raises:
      RuntimeError: Future attached to a different loop

Fix: dispose the inherited engine pool inside run_async() before creating a new
event loop. This forces SQLAlchemy to create fresh asyncpg connections on the
new loop. The dispose() call is cheap — it doesn't close existing connections
in other processes, just resets the pool in this process.

Pipeline order:
  1. Ingest (RSS/GNews) → articles table
  2. Embed (Gemini/OpenAI) → Qdrant + articles.embedding_status
  3. Extract Events (Gemini/OpenAI) → article_events table
  4. Cluster (HDBSCAN + incremental) → stories table

Observability:
  Each task is wrapped with PipelineRun + StageSpan context managers
  that emit trace_id, run_id, stage, latency, and error data.
"""

import asyncio
import logging
import uuid
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.core.trace import (
    PipelineRun,
    PipelineStage,
    StageSpan,
    bind_article_context,
)
from app.models.models import Article, ArticleEntity, ArticleEvent
from app.services.embedding_service import embedding_service
from app.services.ingestion_service import ingestion_service
from app.services.vector_service import vector_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Cooldown duration (seconds) when all LLM providers are quota-exhausted
_QUOTA_COOLDOWN_SECONDS = 3600  # 1 hour


async def _pause_pipeline_for_quota_cooldown(stage: str) -> None:
    """Set the pipeline_paused flag in Redis for _QUOTA_COOLDOWN_SECONDS.

    Called automatically when every provider in the LLM fallback chain returns
    a quota / rate-limit error so Celery Beat stops firing AI-heavy tasks.
    The flag has a TTL equal to the cooldown duration and is automatically
    cleared by the cache expiry — no manual resume needed.
    """
    try:
        from app.services.cache_service import cache_service

        await cache_service.set("pipeline_paused", "True", ttl=_QUOTA_COOLDOWN_SECONDS)
        logger.warning(
            "Pipeline auto-paused for %d seconds due to quota exhaustion at stage '%s'. "
            "Will auto-resume after TTL expires.",
            _QUOTA_COOLDOWN_SECONDS,
            stage,
        )
    except Exception as cache_err:
        logger.error("Failed to set pipeline_paused flag: %s", cache_err)


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from a synchronous Celery prefork worker.

    CRITICAL: Disposes the inherited SQLAlchemy connection pool so that the
    new event loop gets fresh asyncpg connections instead of ones bound to
    the parent's loop. Without this, every task raises:
        RuntimeError: Task got Future attached to a different loop
    """
    import time

    from celery import current_task

    start_perf = time.perf_counter()

    # Try to measure Celery queue latency (lag between ETA/creation and worker execution start)
    try:
        if current_task and current_task.request:
            req = current_task.request
            eta = req.eta
            if eta:
                from datetime import datetime

                now_utc = datetime.now(UTC)
                if isinstance(eta, datetime):
                    # Ensure tz-aware comparison
                    if eta.tzinfo is None:
                        eta = eta.replace(tzinfo=UTC)
                    queue_delay = (now_utc - eta).total_seconds()
                    if queue_delay > 0:
                        from app.core.metrics import newsiq_task_queue_time_seconds

                        newsiq_task_queue_time_seconds.labels(
                            task_name=current_task.name or "unknown"
                        ).observe(queue_delay)
    except Exception as e:
        logger.debug("Failed to record task queue delay: %s", e)

    # 1. Dispose the inherited engine pool — resets pool state in this fork.
    #    New connections will be created on the new event loop below.
    try:
        # engine.sync_engine is the underlying synchronous Engine
        engine.sync_engine.dispose(close=False)
    except Exception:
        pass  # Best-effort

    # 2. Create a clean event loop for this task invocation
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # Measure and record task worker execution latency
        try:
            if current_task and current_task.name:
                duration = time.perf_counter() - start_perf
                from app.core.metrics import newsiq_task_worker_time_seconds

                newsiq_task_worker_time_seconds.labels(task_name=current_task.name).observe(
                    duration
                )
        except Exception as e:
            logger.debug("Failed to record task worker duration: %s", e)

        # 3. Cancel any lingering tasks and close the loop
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(None)


async def is_pipeline_paused() -> bool:
    try:
        from app.services.cache_service import cache_service

        is_paused = await cache_service.get("pipeline_paused")
        return bool(is_paused)
    except Exception:
        return False


@celery_app.task(name="app.workers.tasks.ingest_news_task")
def ingest_news_task(run_id: str | None = None, trace_id: str | None = None) -> dict[str, int]:
    """Ingest articles from all active RSS news sources."""
    logger.info("Celery task: Starting RSS news ingestion.")

    async def _run():
        if await is_pipeline_paused():
            logger.info("Pipeline is paused. Skipping RSS news ingestion.")
            return {}

        async with PipelineRun(
            trigger="celery_beat", pipeline_type="incremental", run_id=run_id, trace_id=trace_id
        ) as run:
            async with StageSpan(run, stage=PipelineStage.INGESTION_RSS) as span:
                async with async_session_factory() as session:
                    results = await ingestion_service.ingest_all_active_sources(session)
                    total_new = sum(results.values())

                    # Generate daily/hourly/rolling discovery report and log it
                    discovery_report = {}
                    disc_persisted = 0
                    try:
                        from app.services.gnews_service import gnews_service

                        discovery_report = await gnews_service.generate_discovery_reports(session)
                        # The persisted count is from today's daily report
                        disc_persisted = discovery_report.get("daily", {}).get(
                            "articles_persisted", 0
                        )
                    except Exception as report_exc:
                        logger.error("Failed to generate discovery reports: %s", report_exc)

                    span.set_metadata(
                        {
                            "articles_ingested": total_new,
                            "sources_processed": len(results),
                            "per_source": {str(k): v for k, v in results.items()},
                            "discovery": discovery_report,
                        }
                    )
                    # We trigger embedding task if either new RSS articles OR discovered articles were persisted!
                    total_including_discovery = total_new + disc_persisted
                    if total_including_discovery > 0:
                        logger.info(
                            "RSS ingestion and discovery complete",
                            extra={
                                "articles_ingested": total_new,
                                "discovery_persisted": disc_persisted,
                            },
                        )
                        process_pending_embeddings_task.delay(run.id, run.trace_id)
                    else:
                        span.mark_skipped()
                    return results

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.ingest_gnews_task")
def ingest_gnews_task(run_id: str | None = None, trace_id: str | None = None) -> dict[str, int]:
    """Ingest articles from the GNews API across configured categories and countries.

    Rate-limit guard is handled inside GNewsService via Redis TTL locks.
    Runs every 30 minutes (48 requests/day, well within free-tier 100 req/day limit).
    """
    logger.info("Celery task: Starting GNews API ingestion.")

    async def _run():
        if await is_pipeline_paused():
            logger.info("Pipeline is paused. Skipping GNews API ingestion.")
            return {}

        from app.services.gnews_service import gnews_service

        async with PipelineRun(
            trigger="celery_beat", pipeline_type="incremental", run_id=run_id, trace_id=trace_id
        ) as run:
            async with StageSpan(run, stage=PipelineStage.INGESTION_GNEWS) as span:
                async with async_session_factory() as session:
                    results = await gnews_service.ingest_all(session)
                    total_new = sum(results.values())
                    span.set_metadata(
                        {
                            "articles_ingested": total_new,
                            "categories_fetched": len(results),
                        }
                    )
                    if total_new > 0:
                        logger.info(
                            "GNews ingestion complete",
                            extra={"articles_ingested": total_new},
                        )
                        process_pending_embeddings_task.delay(run.id, run.trace_id)
                    else:
                        span.mark_skipped()
                    return results

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.process_pending_embeddings_task")
def process_pending_embeddings_task(run_id: str | None = None, trace_id: str | None = None) -> int:
    """Process pending article embeddings, vectorizing and storing in Qdrant."""
    logger.info("Celery task: Processing pending article embeddings.")

    async def _run():
        if await is_pipeline_paused():
            logger.info("Pipeline is paused. Skipping pending article embeddings.")
            return 0

        async with PipelineRun(
            trigger="chained", pipeline_type="incremental", run_id=run_id, trace_id=trace_id
        ) as run:
            async with StageSpan(run, stage=PipelineStage.EMBEDDING) as span:
                async with async_session_factory() as session:
                    # Fetch pending articles
                    stmt = select(Article).where(Article.embedding_status == "pending").limit(50)
                    result = await session.execute(stmt)
                    pending_articles = result.scalars().all()

                    if not pending_articles:
                        logger.info("No pending articles to embed.")
                        span.mark_skipped()
                        return 0

                    logger.info(
                        "Embedding batch started",
                        extra={"batch_size": len(pending_articles)},
                    )
                    # 1. Update all to "processing" first to avoid double processing
                    for article in pending_articles:
                        article.embedding_status = "processing"
                    await session.commit()

                    # 2. Reconstruct texts to embed
                    texts_to_embed = []
                    for article in pending_articles:
                        text_parts = [
                            article.title or "",
                            article.description or "",
                            (article.content or "")[:4000],
                        ]
                        text_to_embed = " ".join(p for p in text_parts if p).strip()
                        if not text_to_embed:
                            text_to_embed = "Empty news article"
                        texts_to_embed.append(text_to_embed)

                    success_count = 0
                    failed_count = 0
                    vectors = []

                    # 3. Call get_embeddings in batch (handles Redis cache lookups + provider API batch call)
                    try:
                        vectors = await embedding_service.get_embeddings(texts_to_embed)
                    except Exception as e:
                        logger.error("Failed to generate batch embeddings: %s", e)

                    # 4. Upsert to Qdrant and update status in-memory.
                    # Single commit at the end instead of one per article (B12 fix).
                    for i, article in enumerate(pending_articles):
                        bind_article_context(str(article.id))
                        if i < len(vectors):
                            vector = vectors[i]
                            try:
                                # Prepare metadata payload for Qdrant
                                payload = {
                                    "title": article.title,
                                    "url": article.url,
                                    "source_id": str(article.source_id),
                                    "published_at": article.published_at.isoformat()
                                    if article.published_at
                                    else None,
                                }

                                # Upsert to Qdrant
                                await vector_service.upsert_article(
                                    article_id=article.id,
                                    vector=vector,
                                    payload=payload,
                                )

                                # Mark as completed in-memory — committed below
                                article.embedding_status = "completed"
                                success_count += 1
                            except Exception as e:
                                logger.error(
                                    "Upsert to Qdrant failed",
                                    extra={
                                        "article_id": str(article.id),
                                        "error": str(e),
                                    },
                                )
                                article.embedding_status = "failed"
                                failed_count += 1
                        else:
                            # Batch embedding did not return a vector for this article
                            logger.error(
                                "No embedding returned for article",
                                extra={"article_id": str(article.id)},
                            )
                            article.embedding_status = "failed"
                            failed_count += 1

                    # Single batch commit for all status updates
                    await session.commit()

                    span.set_metadata(
                        {
                            "batch_size": len(pending_articles),
                            "success_count": success_count,
                            "failed_count": failed_count,
                        }
                    )

                    logger.info(
                        "Embedding batch complete",
                        extra={
                            "success": success_count,
                            "failed": failed_count,
                            "total": len(pending_articles),
                        },
                    )

                    if success_count > 0:
                        # Trigger event extraction for newly embedded articles
                        extract_events_task.delay(run.id, run.trace_id)

                    # If we processed a full batch, check for more
                    if len(pending_articles) == 50:
                        process_pending_embeddings_task.delay(run.id, run.trace_id)

                    return success_count

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.extract_events_task")
def extract_events_task(run_id: str | None = None, trace_id: str | None = None) -> int:
    """Extract structured events from articles that haven't been processed yet.

    Pipeline step: runs AFTER embedding, BEFORE clustering.
    Stores results in article_events table for use in multi-signal clustering.
    """
    logger.info("Celery task: Extracting events from pending articles.")

    async def _run():
        if await is_pipeline_paused():
            logger.info("Pipeline is paused. Skipping event extraction.")
            return 0

        from app.services.event_service import event_service
        from app.services.event_taxonomy import get_parent_type

        async with PipelineRun(
            trigger="chained", pipeline_type="incremental", run_id=run_id, trace_id=trace_id
        ) as run:
            async with StageSpan(run, stage=PipelineStage.EVENT_EXTRACTION) as span:
                async with async_session_factory() as session:
                    # Find articles that are embedded but not yet event-extracted
                    stmt = (
                        select(Article)
                        .where(
                            Article.embedding_status == "completed",
                            Article.event_extraction_status.in_(["pending", None]),
                        )
                        .limit(20)
                    )
                    result = await session.execute(stmt)
                    articles = list(result.scalars().all())

                    if not articles:
                        logger.info("No articles pending event extraction.")
                        span.mark_skipped()
                        return 0

                    logger.info(
                        "Event extraction batch started",
                        extra={"batch_size": len(articles)},
                    )
                    success_count = 0
                    failed_count = 0
                    merged_count = 0

                    for article in articles:
                        bind_article_context(str(article.id))
                        try:
                            # Mark as processing in-memory — no commit here.
                            # The final commit below will persist the terminal status
                            # ("completed" or "failed") in a single round-trip.
                            article.event_extraction_status = "processing"

                            # Extract structured events
                            content = article.content or article.description or ""
                            pub_at = (
                                article.published_at.isoformat() if article.published_at else None
                            )
                            event_response = await event_service.extract_events(
                                title=article.title or "",
                                content=content,
                                published_at=pub_at,
                            )

                            # Store primary event with fingerprint
                            pe = event_response.primary_event
                            parsed_time = _try_parse_event_time(pe.event_time)
                            fingerprint = event_service.compute_event_fingerprint(pe)

                            primary_event = ArticleEvent(
                                id=uuid.uuid4(),
                                article_id=article.id,
                                is_primary=True,
                                event_type=pe.event_type,
                                event_type_canonical=get_parent_type(pe.event_type),
                                actors=pe.actors,
                                targets=pe.targets,
                                objects=pe.objects,
                                location=pe.location,
                                event_time=parsed_time,
                                event_time_raw=pe.event_time,
                                numbers=pe.numbers,
                                confidence=pe.confidence,
                                event_fingerprint=fingerprint,
                            )
                            session.add(primary_event)

                            # Store secondary events
                            for se in event_response.secondary_events[:3]:
                                parsed_time_s = _try_parse_event_time(se.event_time)
                                secondary_event = ArticleEvent(
                                    id=uuid.uuid4(),
                                    article_id=article.id,
                                    is_primary=False,
                                    event_type=se.event_type,
                                    event_type_canonical=get_parent_type(se.event_type),
                                    actors=se.actors,
                                    targets=se.targets,
                                    objects=se.objects,
                                    location=se.location,
                                    event_time=parsed_time_s,
                                    event_time_raw=se.event_time,
                                    numbers=se.numbers,
                                    confidence=se.confidence,
                                )
                                session.add(secondary_event)

                            # Store per-article entities (from combined extraction)
                            from app.services.entity_linker import entity_linker

                            for ent in event_response.entities[:20]:
                                canonical_entity_id = None
                                try:
                                    canonical_ent = await entity_linker.link_entity(
                                        name=ent.canonical_name or ent.value,
                                        entity_type=ent.type,
                                        context=(article.title or "")
                                        + " "
                                        + (article.description or ""),
                                        session=session,
                                    )
                                    canonical_entity_id = canonical_ent.id
                                except Exception as link_err:
                                    logger.warning(
                                        "Entity linking failed for '%s': %s", ent.value, link_err
                                    )

                                article_entity = ArticleEntity(
                                    id=uuid.uuid4(),
                                    article_id=article.id,
                                    canonical_entity_id=canonical_entity_id,
                                    entity_type=ent.type,
                                    entity_value=ent.value,
                                )
                                session.add(article_entity)

                            article.event_extraction_status = "completed"
                            await session.commit()
                            success_count += 1

                            # Try real-time incremental merge into similar story
                            from app.services.clustering_service import clustering_service

                            merged = (
                                await clustering_service.add_article_to_existing_story_if_similar(
                                    article.id, session
                                )
                            )
                            if merged:
                                merged_count += 1

                        except Exception as e:
                            from app.llm_gateway.request_manager import QuotaExhaustedError

                            if isinstance(e, QuotaExhaustedError):
                                # All LLM providers are quota-exhausted — pause the whole
                                # pipeline for a cooldown period rather than hammering the API.
                                await _pause_pipeline_for_quota_cooldown("event_extraction")
                                logger.warning(
                                    "QuotaExhaustedError: stopping event extraction batch early. "
                                    "Pipeline paused for %d seconds.",
                                    _QUOTA_COOLDOWN_SECONDS,
                                )
                                break  # exit per-article loop

                            logger.error(
                                "Event extraction failed",
                                extra={
                                    "article_id": str(article.id),
                                    "error": str(e),
                                },
                            )
                            article.event_extraction_status = "failed"
                            await session.commit()
                            failed_count += 1

                            # Record Pipeline Failure
                            try:
                                from app.core.failure_recorder import record_pipeline_failure
                                from app.core.trace import _to_uuid, run_id_ctx, trace_id_ctx

                                await record_pipeline_failure(
                                    stage=PipelineStage.EVENT_EXTRACTION,
                                    exception=e,
                                    trace_id=_to_uuid(trace_id_ctx.get("")),
                                    run_id=_to_uuid(run_id_ctx.get("")),
                                    article_id=article.id,
                                    input_payload={
                                        "title": article.title,
                                        "content": (article.content or article.description or "")[
                                            :4000
                                        ],
                                        "published_at": article.published_at.isoformat()
                                        if article.published_at
                                        else None,
                                    },
                                )
                            except Exception as rec_err:
                                logger.error(
                                    "Failed to record event extraction failure: %s", rec_err
                                )

                    span.set_metadata(
                        {
                            "batch_size": len(articles),
                            "success_count": success_count,
                            "failed_count": failed_count,
                            "merged_count": merged_count,
                        }
                    )

                    logger.info(
                        "Event extraction batch complete",
                        extra={
                            "success": success_count,
                            "failed": failed_count,
                            "merged": merged_count,
                            "total": len(articles),
                        },
                    )

                    # If we processed a full batch, check for more
                    if len(articles) == 20:
                        extract_events_task.delay(run.id, run.trace_id)
                    else:
                        # Event extraction for this batch is done. Trigger clustering now.
                        cluster_news_task.delay(run.id, run.trace_id)

                    return success_count

    return run_async(_run())


def _try_parse_event_time(raw: str | None) -> datetime | None:
    """Attempt to parse an event time string to datetime."""
    if not raw or not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    try:
        from dateutil import parser

        return parser.parse(raw).replace(tzinfo=None)
    except Exception:
        return None


@celery_app.task(name="app.workers.tasks.cluster_news_task")
def cluster_news_task(run_id: str | None = None, trace_id: str | None = None) -> int:
    """Run batch clustering of unclustered articles into stories."""
    logger.info("Celery task: Running batch clustering.")

    async def _run():
        if await is_pipeline_paused():
            logger.info("Pipeline is paused. Skipping batch clustering.")
            return 0

        # Distributed lock — prevents two concurrent workers from running
        # batch clustering simultaneously and creating duplicate stories.
        # NX = only set if not exists; TTL = 10 minutes (generous upper bound).
        _CLUSTER_LOCK_KEY = "newsiq:lock:cluster_news_task"
        _CLUSTER_LOCK_TTL = 600  # seconds

        from app.services.cache_service import cache_service

        lock_acquired = True  # default: allow run if Redis unavailable
        try:
            lock_acquired = await cache_service.set_nx(
                _CLUSTER_LOCK_KEY, "1", ttl=_CLUSTER_LOCK_TTL
            )
        except Exception as lock_err:
            logger.warning(
                "Failed to acquire cluster lock (Redis error): %s — proceeding.", lock_err
            )

        if not lock_acquired:
            logger.info(
                "cluster_news_task: lock already held by another worker — skipping this invocation."
            )
            return 0

        try:
            from app.llm_gateway.request_manager import QuotaExhaustedError

            async with PipelineRun(
                trigger="chained", pipeline_type="batch", run_id=run_id, trace_id=trace_id
            ) as run:
                async with StageSpan(run, stage=PipelineStage.CLUSTERING_BATCH) as span:
                    async with async_session_factory() as session:
                        from app.services.clustering_service import clustering_service

                        try:
                            stories_created = await clustering_service.run_batch_clustering(session)
                        except QuotaExhaustedError:
                            await _pause_pipeline_for_quota_cooldown("clustering")
                            logger.warning(
                                "QuotaExhaustedError during clustering. Pipeline paused for %d seconds.",
                                _QUOTA_COOLDOWN_SECONDS,
                            )
                            span.mark_skipped()
                            return 0

                        span.set_metadata(
                            {
                                "stories_created": stories_created,
                            }
                        )
                        if stories_created == 0:
                            span.mark_skipped()
                        logger.info(
                            "Batch clustering complete",
                            extra={"stories_created": stories_created},
                        )
                        return stories_created
        finally:
            # Always release the lock, even on exception
            try:
                await cache_service.delete(_CLUSTER_LOCK_KEY)
            except Exception as lock_err:
                logger.warning("Failed to release cluster lock: %s", lock_err)

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.collect_queue_metrics_task")
def collect_queue_metrics_task() -> None:
    """Collect queue and worker health metrics."""
    from app.services.queue_metrics_collector import collect_queue_metrics

    run_async(collect_queue_metrics())


@celery_app.task(name="app.workers.tasks.replay_story_task")
def replay_story_task(story_id_str: str) -> None:
    """Replay the full pipeline for a specific story."""
    logger.info("Celery task: Replaying full story %s", story_id_str)

    async def _run():
        import uuid

        # Per-story distributed lock — prevents duplicate concurrent replays
        # (e.g., double-click in admin UI or two concurrent API calls).
        # Scoped per story_id so different stories can replay in parallel.
        _REPLAY_LOCK_KEY = f"newsiq:lock:replay:{story_id_str}"
        _REPLAY_LOCK_TTL = 900  # 15 minutes

        from app.services.cache_service import cache_service
        from app.services.replay_service import replay_service

        lock_acquired = True  # fail-open if Redis unavailable
        try:
            lock_acquired = await cache_service.set_nx(_REPLAY_LOCK_KEY, "1", ttl=_REPLAY_LOCK_TTL)
        except Exception as lock_err:
            logger.warning(
                "Failed to acquire replay lock for story %s: %s — proceeding.",
                story_id_str,
                lock_err,
            )

        if not lock_acquired:
            logger.info(
                "replay_story_task: replay already in progress for story %s — skipping.",
                story_id_str,
            )
            return

        try:
            async with async_session_factory() as session:
                await replay_service.replay_full_story(uuid.UUID(story_id_str), session)
        finally:
            try:
                await cache_service.delete(_REPLAY_LOCK_KEY)
            except Exception as lock_err:
                logger.warning(
                    "Failed to release replay lock for story %s: %s", story_id_str, lock_err
                )

    run_async(_run())


@celery_app.task(name="app.workers.tasks.replay_story_stage_task")
def replay_story_stage_task(
    story_id_str: str,
    stage_name: str,
    provider_override: str | None = None,
    model_override: str | None = None,
    article_id_str: str | None = None,
) -> None:
    """Replay a specific stage for a story with optional model/provider overrides."""
    logger.info(
        "Celery task: Replaying stage %s for story %s (overrides: provider=%s, model=%s, article=%s)",
        stage_name,
        story_id_str,
        provider_override,
        model_override,
        article_id_str,
    )

    async def _run():
        import uuid

        from app.llm_gateway.request_manager import model_override_ctx, provider_override_ctx
        from app.services.replay_service import replay_service

        if provider_override:
            provider_override_ctx.set(provider_override)
        if model_override:
            model_override_ctx.set(model_override)

        sid = uuid.UUID(story_id_str)
        aid = uuid.UUID(article_id_str) if article_id_str else None

        async with async_session_factory() as session:
            await replay_service.replay_story_stage(sid, stage_name, session, article_id=aid)

    run_async(_run())


@celery_app.task(name="app.workers.tasks.recover_stuck_embeddings_task")
def recover_stuck_embeddings_task() -> int:
    """Reset articles that got stuck in 'processing' state back to 'pending'."""
    logger.info("Celery task: Running stuck embedding recovery.")

    async def _run():
        from datetime import datetime, timedelta

        from sqlalchemy import update

        from app.models.models import Article

        cutoff = datetime.utcnow() - timedelta(minutes=30)
        async with async_session_factory() as session:
            stmt = (
                update(Article)
                .where(Article.embedding_status == "processing")
                .where(Article.crawled_at < cutoff)
                .values(embedding_status="pending")
            )
            result = await session.execute(stmt)
            await session.commit()
            rowcount = result.rowcount
            if rowcount > 0:
                logger.warning("Recovered %d stuck embedding tasks.", rowcount)
            return rowcount

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.evaluate_story_lifecycles_task")
def evaluate_story_lifecycles_task() -> int:
    """Periodically evaluate transitions for all active stories."""
    logger.info("Celery task: Evaluating story lifecycles.")

    async def _run():
        from app.services.story_lifecycle_service import story_lifecycle_service

        async with async_session_factory() as session:
            count = await story_lifecycle_service.evaluate_all_active_stories(session)
            await session.commit()
            if count > 0:
                logger.info("Transitioned %d stories during periodic evaluation.", count)
            return count

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.aggregate_pipeline_metrics_task")
def aggregate_pipeline_metrics_task() -> dict:
    """Periodically compute and cache comprehensive pipeline dashboard metrics in Redis."""
    logger.info("Celery task: Aggregating pipeline dashboard metrics.")

    async def _run():
        from app.services.admin_service import admin_service

        async with async_session_factory() as session:
            return await admin_service.compute_dashboard_metrics(session)

    return run_async(_run())


async def _check_discovery_task_completion(discovery_task_id: uuid.UUID, session: Any) -> None:
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.models.models import CrawlTask, CrawlTaskState, DiscoveryTask, DiscoveryTaskState

    # Get total count of CrawlTasks for this DiscoveryTask
    stmt = select(CrawlTask).where(CrawlTask.discovery_task_id == discovery_task_id)
    res = await session.execute(stmt)
    crawl_tasks = list(res.scalars().all())

    if not crawl_tasks:
        return

    all_done = True
    for ct in crawl_tasks:
        if ct.status not in (CrawlTaskState.SUCCESS, CrawlTaskState.FAILED):
            all_done = False
            break

    if all_done:
        # All completed! Update parent DiscoveryTask
        parent_stmt = select(DiscoveryTask).where(DiscoveryTask.id == discovery_task_id)
        parent_res = await session.execute(parent_stmt)
        parent_task = parent_res.scalar_one_or_none()
        if parent_task and parent_task.status != DiscoveryTaskState.COMPLETE:
            parent_task.status = DiscoveryTaskState.COMPLETE
            parent_task.completed_at = datetime.now(UTC).replace(tzinfo=None)
            logger.info(
                "DiscoveryTask %s marked COMPLETE (all crawl tasks completed)", discovery_task_id
            )


@celery_app.task(name="app.workers.tasks.discovery_search_task")
def discovery_search_task(
    discovery_task_id_str: str, run_id: str | None = None, trace_id: str | None = None
) -> None:
    """Execute search discovery using persistent database tasks and separate search queues."""
    logger.info("Celery task: Running search discovery for Task %s", discovery_task_id_str)

    async def _run():
        import hashlib
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import select

        from app.core.config import settings
        from app.ingestion import get_discovery_provider
        from app.models.models import (
            Article,
            CrawlTask,
            CrawlTaskState,
            DiscoveryTask,
            DiscoveryTaskState,
        )
        from app.services.cache_service import cache_service
        from app.services.gnews_service import gnews_service

        discovery_task_id = uuid.UUID(discovery_task_id_str)

        async with async_session_factory() as session:
            # 1. Load DiscoveryTask
            stmt = select(DiscoveryTask).where(DiscoveryTask.id == discovery_task_id)
            res = await session.execute(stmt)
            task = res.scalar_one_or_none()
            if not task:
                logger.error("DiscoveryTask %s not found.", discovery_task_id_str)
                return

            if task.status != DiscoveryTaskState.PENDING:
                logger.info(
                    "DiscoveryTask %s is not PENDING (current status: %s). Skipping.",
                    discovery_task_id_str,
                    task.status,
                )
                return

            # 2. Check Daily Search Budget
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            budget_key = f"discovery:daily_searches_run:{date_str}"
            try:
                current_searches = int(await cache_service.get(budget_key) or 0)
                if current_searches >= settings.DISCOVERY_DAILY_SEARCH_BUDGET:
                    logger.warning(
                        "Daily discovery search budget exceeded (%d/%d). Expiring task %s.",
                        current_searches,
                        settings.DISCOVERY_DAILY_SEARCH_BUDGET,
                        discovery_task_id_str,
                    )
                    task.status = DiscoveryTaskState.EXPIRED
                    task.last_error = "Daily search budget exceeded"
                    await session.commit()
                    return
            except Exception as e:
                logger.warning("Failed to check search budget: %s", e)

            # 3. Load associated Article to get original details for ranking
            art_stmt = select(Article).where(Article.id == task.article_id)
            art_res = await session.execute(art_stmt)
            original_article = art_res.scalar_one_or_none()
            if not original_article:
                logger.error(
                    "Original article %s not found for DiscoveryTask %s.",
                    task.article_id,
                    discovery_task_id_str,
                )
                task.status = DiscoveryTaskState.SEARCH_FAILED
                task.last_error = "Original article not found"
                await session.commit()
                return

            # 4. Acquire distributed lock with date bucket to avoid duplicate queries
            query_hash = hashlib.sha256(task.query.encode("utf-8")).hexdigest()
            lock_key = f"discovery:search_lock:{task.provider}:{query_hash}:{date_str}"
            try:
                acquired = await cache_service.set(lock_key, "1", ttl=600, nx=True)
                if not acquired:
                    logger.info(
                        "Duplicate search lock hit for query '%s' on provider %s. Expiring task %s.",
                        task.query,
                        task.provider,
                        discovery_task_id_str,
                    )
                    task.status = DiscoveryTaskState.EXPIRED
                    task.last_error = "Duplicate search lock hit"
                    await session.commit()
                    return
            except Exception as e:
                logger.warning("Failed to check search lock: %s", e)

            # 5. Transition to SEARCHING
            task.status = DiscoveryTaskState.SEARCHING
            task.search_started_at = datetime.now(UTC).replace(tzinfo=None)
            task.queued_at = (
                datetime.now(UTC).replace(tzinfo=None) if not task.queued_at else task.queued_at
            )
            await session.flush()

            # Increment search count in Redis
            try:
                await cache_service.set(budget_key, str(current_searches + 1), ttl=36 * 3600)
            except Exception as e:
                logger.warning("Failed to increment search budget counter: %s", e)

            # 6. Execute Provider Search
            try:
                provider = get_discovery_provider(task.provider)
                raw_results = await asyncio.wait_for(
                    provider.search(
                        query=task.query, max_results=settings.DISCOVERY_MAX_RESULTS * 3
                    ),
                    timeout=5.0,
                )

                # Rank results and apply base domain diversity filtering
                discovered_urls = gnews_service.rank_and_filter_search_results(
                    results=raw_results,
                    original_title=original_article.title,
                    original_pub_date=original_article.published_at,
                    max_results=settings.DISCOVERY_MAX_RESULTS,
                )

                task.search_completed_at = datetime.now(UTC).replace(tzinfo=None)

            except Exception as e:
                logger.error(
                    "Discovery search provider failed for task %s: %s", discovery_task_id_str, e
                )
                task.retry_count += 1
                if task.retry_count < settings.DISCOVERY_MAX_RETRIES:
                    task.status = DiscoveryTaskState.PENDING
                    task.next_retry_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                        minutes=2**task.retry_count
                    )
                    task.last_error = f"Search failed: {str(e)}"
                else:
                    task.status = DiscoveryTaskState.SEARCH_FAILED
                    task.last_error = f"Search failed (max retries exceeded): {str(e)}"
                await session.commit()
                return

            # 7. Create CrawlTasks for found URLs
            if not discovered_urls:
                logger.info(
                    "No URLs discovered for query '%s'. Completing task %s.",
                    task.query,
                    discovery_task_id_str,
                )
                task.status = DiscoveryTaskState.COMPLETE
                task.completed_at = datetime.now(UTC).replace(tzinfo=None)
                await session.commit()
                return

            task.status = DiscoveryTaskState.CRAWLING
            task.completed_at = None

            from app.core.fingerprint import compute_fingerprints

            created_crawl_task_ids = []

            for url in discovered_urls:
                url_canonical = (
                    gnews_service.canonicalize_url(url)
                    if hasattr(gnews_service, "canonicalize_url")
                    else url
                )
                url_hash = compute_fingerprints(url_canonical, "", "")["url_hash"]

                new_crawl_task = CrawlTask(
                    discovery_task_id=task.id,
                    url=url_canonical,
                    url_hash=url_hash,
                    status=CrawlTaskState.PENDING,
                    task_version=2,
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                )
                session.add(new_crawl_task)
                await session.flush()
                created_crawl_task_ids.append(new_crawl_task.id)

            await session.commit()

            # Dispatch crawl tasks
            for ct_id in created_crawl_task_ids:
                discovery_crawl_task.delay(str(ct_id), run_id, trace_id)

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.discovery_crawl_task")
def discovery_crawl_task(
    crawl_task_id_str: str, run_id: str | None = None, trace_id: str | None = None
) -> None:
    """Crawl, clean, validate, and persist a single discovered URL."""
    logger.info("Celery task: Crawling discovered URL for CrawlTask %s", crawl_task_id_str)

    async def _run():
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import select

        from app.core.config import settings
        from app.core.fingerprint import compute_fingerprints
        from app.models.models import Article, CrawlTask, CrawlTaskState
        from app.services.cache_service import cache_service
        from app.services.clustering_service import clustering_service
        from app.services.crawler_service import crawler_service
        from app.services.gnews_service import gnews_service
        from app.services.ingestion_service import url_bloom_filter

        crawl_task_id = uuid.UUID(crawl_task_id_str)

        async with async_session_factory() as session:
            # 1. Load CrawlTask
            stmt = select(CrawlTask).where(CrawlTask.id == crawl_task_id)
            res = await session.execute(stmt)
            crawl_task = res.scalar_one_or_none()
            if not crawl_task:
                logger.error("CrawlTask %s not found.", crawl_task_id_str)
                return

            if crawl_task.status not in (CrawlTaskState.PENDING, CrawlTaskState.RETRYING):
                logger.info(
                    "CrawlTask %s is not in processable state (current status: %s). Skipping.",
                    crawl_task_id_str,
                    crawl_task.status,
                )
                return

            # 2. Check Daily Download Budget
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            budget_key = f"discovery:daily_downloads_run:{date_str}"
            try:
                current_downloads = int(await cache_service.get(budget_key) or 0)
                if current_downloads >= settings.DISCOVERY_DAILY_DOWNLOAD_BUDGET:
                    logger.warning(
                        "Daily download budget exceeded (%d/%d). Failing CrawlTask %s.",
                        current_downloads,
                        settings.DISCOVERY_DAILY_DOWNLOAD_BUDGET,
                        crawl_task_id_str,
                    )
                    crawl_task.status = CrawlTaskState.FAILED
                    crawl_task.outcome = "BUDGET_EXCEEDED"
                    crawl_task.last_error = "Daily download budget exceeded"
                    await session.commit()
                    await _check_discovery_task_completion(crawl_task.discovery_task_id, session)
                    await session.commit()
                    return
            except Exception as e:
                logger.warning("Failed to check download budget: %s", e)

            # 3. Early Bloom Filter Check
            if await url_bloom_filter.exists(crawl_task.url_hash):
                logger.info(
                    "Bloom Filter skip hit for CrawlTask %s (URL: %s)",
                    crawl_task_id_str,
                    crawl_task.url,
                )
                crawl_task.status = CrawlTaskState.SUCCESS
                crawl_task.outcome = "BLOOM_SKIP"
                crawl_task.completed_at = datetime.now(UTC).replace(tzinfo=None)
                await session.commit()
                await _check_discovery_task_completion(crawl_task.discovery_task_id, session)
                await session.commit()
                return

            # 4. Update status to CRAWLING
            crawl_task.status = CrawlTaskState.CRAWLING
            crawl_task.crawl_started_at = datetime.now(UTC).replace(tzinfo=None)
            await session.flush()

            # Increment downloads count in Redis
            try:
                await cache_service.set(budget_key, str(current_downloads + 1), ttl=36 * 3600)
            except Exception as e:
                logger.warning("Failed to increment download budget counter: %s", e)

            # 5. Execute HTTP crawl
            try:
                crawled = await crawler_service.crawl_article(crawl_task.url)
                if not crawled or not crawled.get("content"):
                    raise ValueError("Crawl returned empty content")
            except Exception as e:
                logger.warning(
                    "Failed to crawl URL %s for CrawlTask %s: %s",
                    crawl_task.url,
                    crawl_task_id_str,
                    e,
                )
                crawl_task.retry_count += 1
                if crawl_task.retry_count < settings.DISCOVERY_MAX_RETRIES:
                    crawl_task.status = CrawlTaskState.RETRYING
                    crawl_task.next_retry_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                        minutes=2**crawl_task.retry_count
                    )
                    crawl_task.outcome = "RETRYING"
                    crawl_task.last_error = f"Crawl failed: {str(e)}"
                else:
                    crawl_task.status = CrawlTaskState.FAILED
                    crawl_task.outcome = "FAILED"
                    crawl_task.last_error = f"Crawl failed (max retries exceeded): {str(e)}"
                await session.commit()
                await _check_discovery_task_completion(crawl_task.discovery_task_id, session)
                await session.commit()
                return

            # 6. Database checks (sequential)
            dup_stmt = select(Article).where(Article.url == crawl_task.url)
            dup_res = await session.execute(dup_stmt)
            if dup_res.scalar_one_or_none():
                logger.info("Exact URL duplicate found in DB for CrawlTask %s", crawl_task_id_str)
                await url_bloom_filter.add(crawl_task.url_hash)
                crawl_task.status = CrawlTaskState.SUCCESS
                crawl_task.outcome = "DUPLICATE_URL"
                crawl_task.completed_at = datetime.now(UTC).replace(tzinfo=None)
                await session.commit()
                await _check_discovery_task_completion(crawl_task.discovery_task_id, session)
                await session.commit()
                return

            title = crawled.get("title") or "Untitled Discovered Article"
            content = crawled.get("content")
            fingerprints = compute_fingerprints(crawl_task.url, title, content)
            content_hash = fingerprints["content_hash"]

            dup_content_stmt = select(Article).where(Article.content_hash == content_hash)
            dup_content_res = await session.execute(dup_content_stmt)
            if dup_content_res.scalar_one_or_none():
                logger.info(
                    "Content hash duplicate found in DB for CrawlTask %s", crawl_task_id_str
                )
                await url_bloom_filter.add(crawl_task.url_hash)
                crawl_task.status = CrawlTaskState.SUCCESS
                crawl_task.outcome = "DUPLICATE_CONTENT"
                crawl_task.completed_at = datetime.now(UTC).replace(tzinfo=None)
                await session.commit()
                await _check_discovery_task_completion(crawl_task.discovery_task_id, session)
                await session.commit()
                return

            # 7. Resolve Source & Persist Article
            source = await gnews_service._resolve_source(
                gnews_source_name=None, gnews_source_url=crawl_task.url, session=session
            )
            if not source:
                from urllib.parse import urlparse

                domain = urlparse(crawl_task.url).netloc or "discovered_source"
                source = await gnews_service._resolve_source(
                    gnews_source_name=domain.replace("www.", ""),
                    gnews_source_url=f"http://{domain}",
                    session=session,
                )

            new_article = Article(
                source_id=source.id if source else None,
                title=title,
                description=crawled.get("description") or title,
                content=content,
                url=crawl_task.url,
                author=crawled.get("author"),
                language="en",
                image_url=crawled.get("image_url"),
                published_at=crawled.get("published_at") or datetime.now(UTC).replace(tzinfo=None),
                crawled_at=datetime.now(UTC).replace(tzinfo=None),
                content_hash=content_hash,
                title_hash=fingerprints["title_hash"],
                simhash_text=fingerprints.get("simhash"),
                embedding_status="pending",
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(new_article)
            await session.flush()

            crawl_task.status = CrawlTaskState.SUCCESS
            crawl_task.outcome = "SUCCESS"
            crawl_task.article_id = new_article.id
            crawl_task.completed_at = datetime.now(UTC).replace(tzinfo=None)

            await url_bloom_filter.add(crawl_task.url_hash)
            await session.commit()

            # Downstream matching
            try:
                await clustering_service.add_article_to_existing_story_if_similar(
                    article_id=new_article.id, session=session
                )
                await session.commit()
            except Exception as e:
                logger.error(
                    "Failed to run downstream match coordinator for article %s: %s",
                    new_article.id,
                    e,
                )

            await _check_discovery_task_completion(crawl_task.discovery_task_id, session)
            await session.commit()

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.poll_discovery_retries_task")
def poll_discovery_retries_task() -> dict[str, int]:
    """Poll the database for overdue PENDING/RETRYING tasks and re-dispatch them."""
    logger.info("Celery task: Polling discovery retries.")

    async def _run():
        from datetime import UTC, datetime

        from sqlalchemy import select

        from app.models.models import CrawlTask, CrawlTaskState, DiscoveryTask, DiscoveryTaskState

        counts = {"search_retries": 0, "crawl_retries": 0}
        now = datetime.now(UTC).replace(tzinfo=None)

        async with async_session_factory() as session:
            # 1. Poll DiscoveryTasks that are due for retry
            stmt = select(DiscoveryTask).where(
                DiscoveryTask.status == DiscoveryTaskState.PENDING,
                DiscoveryTask.next_retry_at <= now,
            )
            res = await session.execute(stmt)
            tasks = res.scalars().all()
            for t in tasks:
                t.queued_at = now
                discovery_search_task.delay(str(t.id))
                counts["search_retries"] += 1

            # 2. Poll CrawlTasks that are due for retry
            crawl_stmt = select(CrawlTask).where(
                CrawlTask.status == CrawlTaskState.RETRYING, CrawlTask.next_retry_at <= now
            )
            crawl_res = await session.execute(crawl_stmt)
            crawl_tasks = crawl_res.scalars().all()
            for ct in crawl_tasks:
                ct.status = CrawlTaskState.PENDING
                ct.outcome = "RETRYING"
                discovery_crawl_task.delay(str(ct.id))
                counts["crawl_retries"] += 1

            if counts["search_retries"] > 0 or counts["crawl_retries"] > 0:
                await session.commit()
                logger.info(
                    "Re-enqueued %d search discovery tasks and %d crawl tasks for retry.",
                    counts["search_retries"],
                    counts["crawl_retries"],
                )
            return counts

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.cleanup_discovery_tasks_task")
def cleanup_discovery_tasks_task() -> dict[str, int]:
    """Delete old completed/failed/expired tasks according to retention policies."""
    logger.info("Celery task: Cleaning up old discovery tasks.")

    async def _run():
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import delete

        from app.models.models import DiscoveryTask

        now = datetime.now(UTC).replace(tzinfo=None)
        boundary_complete = now - timedelta(days=30)
        boundary_failed = now - timedelta(days=14)
        boundary_expired = now - timedelta(days=7)

        async with async_session_factory() as session:
            # 1. Complete tasks
            stmt_complete = delete(DiscoveryTask).where(
                DiscoveryTask.status == "complete", DiscoveryTask.created_at <= boundary_complete
            )
            res_complete = await session.execute(stmt_complete)
            count_complete = getattr(res_complete, "rowcount", 0) or 0

            # 2. Failed tasks
            stmt_failed = delete(DiscoveryTask).where(
                DiscoveryTask.status.in_(["search_failed", "crawl_failed"]),
                DiscoveryTask.created_at <= boundary_failed,
            )
            res_failed = await session.execute(stmt_failed)
            count_failed = getattr(res_failed, "rowcount", 0) or 0

            # 3. Expired tasks
            stmt_expired = delete(DiscoveryTask).where(
                DiscoveryTask.status == "expired", DiscoveryTask.created_at <= boundary_expired
            )
            res_expired = await session.execute(stmt_expired)
            count_expired = getattr(res_expired, "rowcount", 0) or 0

            total_deleted = count_complete + count_failed + count_expired
            if total_deleted > 0:
                await session.commit()
                logger.info(
                    "Discovery GC deleted %d tasks (Complete: %d, Failed: %d, Expired: %d).",
                    total_deleted,
                    count_complete,
                    count_failed,
                    count_expired,
                )

            return {
                "deleted_complete": count_complete,
                "deleted_failed": count_failed,
                "deleted_expired": count_expired,
                "total_deleted": total_deleted,
            }

    return run_async(_run())
