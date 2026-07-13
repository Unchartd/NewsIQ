import asyncio
import logging
import sys

from app.core.database import async_session_factory
from app.services.ingestion_service import ingestion_service

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("run_ingestion_local")

async def main():
    logger.info("Starting local news ingestion with search discovery...")
    async with async_session_factory() as session:
        # Run RSS ingestion + search discovery
        results = await ingestion_service.ingest_all_active_sources(session)
        logger.info("RSS Ingestion Results: %s", results)
        
        # Log discovery metadata
        metadata = getattr(ingestion_service, "last_discovery_metadata", [])
        logger.info("Search Discovery Runs: %d", len(metadata))
        for idx, item in enumerate(metadata):
            logger.info("Run %d: %s", idx + 1, item)

if __name__ == "__main__":
    asyncio.run(main())
