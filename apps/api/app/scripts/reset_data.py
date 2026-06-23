"""Data reset script — clears all stories, articles, events, traces, search index, Qdrant vectors, and Redis cache.

Run with:
    docker compose exec -T user-api env PYTHONPATH=. python -m app.scripts.reset_data
"""

import asyncio
import logging
from sqlalchemy import text
import redis

from app.core.database import async_session_factory
from app.core.config import settings
from app.services.search_service import SearchService, INDEX_NAME
from app.services.vector_service import vector_service, COLLECTION_NAME

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_data")

TABLES_TO_TRUNCATE = [
    "story_metrics",
    "story_timeline_events",
    "story_source_coverage",
    "story_differences",
    "story_contradictions",
    "story_tags",
    "story_entities",
    "story_articles",
    "bookmarks",
    "user_events",
    "search_history",
    "notifications",
    "stories",
    "article_events",
    "article_entities",
    "canonical_entities",
    "articles",
    "llm_traces"
]

async def reset_database():
    logger.info("Connecting to PostgreSQL and truncating tables...")
    async with async_session_factory() as session:
        # Join table names and truncate with CASCADE
        tables_str = ", ".join(TABLES_TO_TRUNCATE)
        query = text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE;")
        await session.execute(query)
        await session.commit()
    logger.info("PostgreSQL tables truncated successfully.")

async def reset_meilisearch():
    logger.info("Connecting to Meilisearch and clearing documents...")
    search = SearchService()
    if search.enabled and search._client:
        try:
            index = search._client.index(INDEX_NAME)
            await index.delete_all_documents()
            logger.info("Meilisearch stories index cleared.")
        except Exception as e:
            logger.error("Failed to clear Meilisearch: %s", e)
    else:
        logger.info("Meilisearch not enabled or client not initialized.")

async def reset_qdrant():
    logger.info("Connecting to Qdrant and dropping collection...")
    try:
        exists = await vector_service.client.collection_exists(collection_name=COLLECTION_NAME)
        if exists:
            await vector_service.client.delete_collection(collection_name=COLLECTION_NAME)
            logger.info("Qdrant collection '%s' deleted.", COLLECTION_NAME)
        # Re-initialize collection
        await vector_service.init_collection()
        logger.info("Qdrant collection '%s' re-created.", COLLECTION_NAME)
    except Exception as e:
        logger.error("Failed to clear Qdrant: %s", e)

def reset_redis():
    logger.info("Connecting to Redis and flushing all caches...")
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.flushall()
        logger.info("Redis flushed successfully (all DBs).")
    except Exception as e:
        logger.error("Failed to flush Redis: %s", e)

async def main():
    logger.info("Starting complete data reset...")
    try:
        await reset_database()
    except Exception as e:
        logger.error("Failed to reset database: %s", e)

    try:
        await reset_meilisearch()
    except Exception as e:
        logger.error("Failed to reset Meilisearch: %s", e)

    try:
        await reset_qdrant()
    except Exception as e:
        logger.error("Failed to reset Qdrant: %s", e)

    reset_redis()
    logger.info("Data reset completed! System is now clean.")

if __name__ == "__main__":
    asyncio.run(main())
