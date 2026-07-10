import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Story
from app.services.clustering_service import clustering_service
from app.services.discovery_manager import DiscoveryManager
from app.services.event_service import event_service
from app.services.story_lifecycle_service import story_lifecycle_service
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)


class PipelineCoordinator:
    """
    Lightweight orchestrator for the AI news pipeline.
    Coordinates: Discovery -> Validation -> Lifecycle -> Identity -> Synthesis.
    Does not implement business logic itself.
    """

    def __init__(self, discovery_manager: DiscoveryManager):
        self.discovery_manager = discovery_manager

    async def process_article(self, session: AsyncSession, article_id: uuid.UUID) -> bool:
        """
        Coordinates the pipeline for a single newly ingested article.
        Returns True if merged into an existing story, False if sent to Discovery.
        """
        logger.info("PipelineCoordinator: Processing article %s", article_id)

        # 1. Validation & Incremental Matching (Stage A & Stage B)
        # Note: add_article_to_existing_story_if_similar handles Candidate Retrieval,
        # Stage A, Embedding (if Stage A passes), Stage B, and LLM Reflection.
        merged_story_id = await clustering_service.add_article_to_existing_story_if_similar(
            article_id=article_id, session=session
        )

        if merged_story_id:
            logger.info(
                "PipelineCoordinator: Article %s merged into Story %s", article_id, merged_story_id
            )

            # 2. Lifecycle & B3 Graduation (automatic via transition logic)
            stmt = select(Story).where(Story.id == uuid.UUID(str(merged_story_id)))
            res = await session.execute(stmt)
            story = res.scalar_one_or_none()
            if story:
                await story_lifecycle_service.evaluate_and_transition(session, story)

            return True

        else:
            logger.info(
                "PipelineCoordinator: Article %s did not match, sending to Discovery", article_id
            )

            # 5. Discovery
            await self.discovery_manager.enqueue_article(session, article_id)
            return False


discovery_manager = DiscoveryManager(vector_service, event_service)
pipeline_coordinator = PipelineCoordinator(discovery_manager)
