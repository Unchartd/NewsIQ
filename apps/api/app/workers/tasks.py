"""Celery background tasks for ingestion, embedding, and clustering.

Architecture note — Celery prefork + asyncpg + Python 3.12:
  Celery uses the prefork pool (fork-based). Each worker child inherits the
  parent's SQLAlchemy async engine whose asyncpg connections are bound to the
  parent's event loop. Reusing them in a forked child raises:
      RuntimeError: Future attached to a different loop

Fix: dispose the inherited engine pool inside run_async() before creating a new
event loop. This forces SQLAlchemy to create fresh asyncpg connections on the
new loop. The dispose() call is cheap — it doesn't close existing connections
in other processes, just resets the pool in this process.
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.models import Article
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

                    # Combine title and description for quality embeddings
                    text_to_embed = f"{article.title or ''} {article.description or ''}".strip()
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
                # Trigger batch clustering to handle newly embedded articles
                cluster_news_task.delay()

            # If we processed a full batch, check for more
            if len(pending_articles) == 50:
                process_pending_embeddings_task.delay()

            return success_count

    return run_async(_run())


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
