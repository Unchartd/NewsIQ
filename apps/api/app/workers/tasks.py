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
"""

import asyncio
import logging
import uuid
from collections.abc import Coroutine
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.models import Article, ArticleEvent
from app.services.embedding_service import embedding_service
from app.services.ingestion_service import ingestion_service
from app.services.vector_service import vector_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from a synchronous Celery prefork worker.

    CRITICAL: Disposes the inherited SQLAlchemy connection pool so that the
    new event loop gets fresh asyncpg connections instead of ones bound to
    the parent's loop. Without this, every task raises:
        RuntimeError: Task got Future attached to a different loop
    """
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


@celery_app.task(name="app.workers.tasks.ingest_news_task")
def ingest_news_task() -> dict[str, int]:
    """Ingest articles from all active RSS news sources."""
    logger.info("Celery task: Starting RSS news ingestion.")

    async def _run():
        async with async_session_factory() as session:
            results = await ingestion_service.ingest_all_active_sources(session)
            total_new = sum(results.values())
            if total_new > 0:
                logger.info("RSS: ingested %d new articles. Triggering embedding.", total_new)
                process_pending_embeddings_task.delay()
            return results

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.ingest_gnews_task")
def ingest_gnews_task() -> dict[str, int]:
    """Ingest articles from the GNews API across configured categories and countries.

    Rate-limit guard is handled inside GNewsService via Redis TTL locks.
    Runs every 30 minutes (48 requests/day, well within free-tier 100 req/day limit).
    """
    logger.info("Celery task: Starting GNews API ingestion.")

    async def _run():
        from app.services.gnews_service import gnews_service

        async with async_session_factory() as session:
            results = await gnews_service.ingest_all(session)
            total_new = sum(results.values())
            if total_new > 0:
                logger.info(
                    "GNews: ingested %d new articles. Triggering embedding pipeline.", total_new
                )
                process_pending_embeddings_task.delay()
            return results

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.process_pending_embeddings_task")
def process_pending_embeddings_task() -> int:
    """Process pending article embeddings, vectorizing and storing in Qdrant."""
    logger.info("Celery task: Processing pending article embeddings.")

    async def _run():
        async with async_session_factory() as session:
            # Fetch pending articles
            stmt = select(Article).where(Article.embedding_status == "pending").limit(50)
            result = await session.execute(stmt)
            pending_articles = result.scalars().all()

            if not pending_articles:
                logger.info("No pending articles to embed.")
                return 0

            logger.info("Embedding batch of %d articles.", len(pending_articles))
            success_count = 0
            merged_count = 0

            from app.services.clustering_service import clustering_service

            for article in pending_articles:
                try:
                    # Update status to processing to avoid double processing
                    article.embedding_status = "processing"
                    await session.commit()

                    # Combine title, description, AND content for quality embeddings
                    # (H3 fix: previously only title+description was embedded)
                    text_parts = [
                        article.title or "",
                        article.description or "",
                        (article.content or "")[:4000],  # Include first 4K of content
                    ]
                    text_to_embed = " ".join(p for p in text_parts if p).strip()
                    if not text_to_embed:
                        text_to_embed = "Empty news article"

                    vector = await embedding_service.get_embedding(text_to_embed)

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

                    # Mark as completed in PostgreSQL
                    article.embedding_status = "completed"
                    await session.commit()
                    success_count += 1

                    # Try real-time incremental merge into similar story
                    merged = await clustering_service.add_article_to_existing_story_if_similar(
                        article.id, session
                    )
                    if merged:
                        merged_count += 1
                except Exception as e:
                    logger.error("Failed to generate embedding for article %s: %s", article.id, e)
                    article.embedding_status = "failed"
                    await session.commit()

            logger.info(
                "Successfully embedded %d/%d articles. Merged %d directly.",
                success_count,
                len(pending_articles),
                merged_count,
            )

            if success_count > 0:
                # Trigger event extraction for newly embedded articles, then clustering
                extract_events_task.delay()
                cluster_news_task.delay()

            # If we processed a full batch, check for more
            if len(pending_articles) == 50:
                process_pending_embeddings_task.delay()

            return success_count

    return run_async(_run())


@celery_app.task(name="app.workers.tasks.extract_events_task")
def extract_events_task() -> int:
    """Extract structured events from articles that haven't been processed yet.

    Pipeline step: runs AFTER embedding, BEFORE clustering.
    Stores results in article_events table for use in multi-signal clustering.
    """
    logger.info("Celery task: Extracting events from pending articles.")

    async def _run():
        from app.services.event_service import event_service
        from app.services.event_taxonomy import get_parent_type

        async with async_session_factory() as session:
            # Find articles that are embedded but not yet event-extracted
            stmt = (
                select(Article)
                .where(
                    Article.embedding_status == "completed",
                    Article.event_extraction_status.in_(["pending", None]),
                )
                .limit(20)  # Smaller batches due to LLM rate limits
            )
            result = await session.execute(stmt)
            articles = list(result.scalars().all())

            if not articles:
                logger.info("No articles pending event extraction.")
                return 0

            logger.info("Extracting events from %d articles.", len(articles))
            success_count = 0

            for article in articles:
                try:
                    article.event_extraction_status = "processing"
                    await session.commit()

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

                    # Store primary event
                    pe = event_response.primary_event
                    parsed_time = _try_parse_event_time(pe.event_time)

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
                    )
                    session.add(primary_event)

                    # Store secondary events
                    for se in event_response.secondary_events[:3]:  # Limit to 3
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

                    article.event_extraction_status = "completed"
                    await session.commit()
                    success_count += 1

                except Exception as e:
                    logger.error(
                        "Event extraction failed for article %s: %s", article.id, e
                    )
                    article.event_extraction_status = "failed"
                    await session.commit()

            logger.info(
                "Event extraction complete: %d/%d articles.",
                success_count,
                len(articles),
            )

            # If we processed a full batch, check for more
            if len(articles) == 20:
                extract_events_task.delay()

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
def cluster_news_task() -> int:
    """Run batch clustering of unclustered articles into stories."""
    logger.info("Celery task: Running batch clustering.")

    async def _run():
        async with async_session_factory() as session:
            from app.services.clustering_service import clustering_service

            stories_created = await clustering_service.run_batch_clustering(session)
            return stories_created

    return run_async(_run())
