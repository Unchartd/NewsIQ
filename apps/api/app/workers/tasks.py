"""Celery background tasks for ingestion, embedding, and clustering."""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.models import Article
from app.services.embedding_service import embedding_service
from app.services.ingestion_service import ingestion_service
from app.services.vector_service import vector_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Helper to run async coroutines in synchronous Celery tasks."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Event loop is already running in this thread
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)


@celery_app.task(name="app.workers.tasks.ingest_news_task")
def ingest_news_task() -> dict[str, int]:
    """Ingest articles from all active news sources."""
    logger.info("Celery task: Starting news ingestion.")

    async def _run():
        async with async_session_factory() as session:
            results = await ingestion_service.ingest_all_active_sources(session)
            # Trigger embedding generation for newly ingested articles
            total_new = sum(results.values())
            if total_new > 0:
                logger.info("Ingested %d new articles. Triggering embedding generation.", total_new)
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
