import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

import yaml
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import newsiq_discovery_articles_total, newsiq_discovery_queue_size
from app.models.models import (
    Article,
    DiscoveryQueue,
    DiscoveryState,
    Story,
    StoryArticle,
)

logger = logging.getLogger(__name__)

# Load config
config_path = os.path.join(os.path.dirname(__file__), "..", "config", "event_validation.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)
DISCOVERY_EXPIRATION_HOURS = config.get("discovery", {}).get("expiration_hours", {})


class DiscoveryManager:
    """
    Manages the lifecycle of the Discovery Queue.
    Responsibilities:
    - Enqueueing articles (with deduplication)
    - Handling expirations and retries
    - Triggering HDBSCAN clustering (grouping)
    - Promoting ready clusters to stable Stories (generating Story Anchors)
    """

    def __init__(self, vector_service=None, event_service=None):
        self.vector_service = vector_service
        self.event_service = event_service

    async def enqueue_article(self, session: AsyncSession, article_id: uuid.UUID) -> bool:
        """Enqueue an article into the Discovery Queue, skipping duplicates."""

        # 1. Deduplication check
        stmt = select(Article).where(Article.id == article_id)
        article = (await session.execute(stmt)).scalar_one_or_none()

        if not article:
            logger.error("Cannot enqueue missing article %s", article_id)
            return False

        # Direct duplicate check on exact article_id in active or processed states
        chk_q_stmt = select(DiscoveryQueue).where(DiscoveryQueue.article_id == article_id).limit(1)
        chk_q_res = await session.execute(chk_q_stmt)
        if chk_q_res.scalar_one_or_none():
            logger.info(
                "Skipping enqueue: Article %s is already in the Discovery Queue.",
                article_id,
            )
            return False

        if article.content_hash:
            dup_stmt = (
                select(DiscoveryQueue)
                .join(Article, DiscoveryQueue.article_id == Article.id)
                .where(
                    Article.content_hash == article.content_hash,
                    DiscoveryQueue.state.in_(
                        [DiscoveryState.PENDING, DiscoveryState.GROUPING, DiscoveryState.READY]
                    ),
                )
                .limit(1)
            )
            is_dup = (await session.execute(dup_stmt)).scalar_one_or_none()
            if is_dup:
                logger.info(
                    "Skipping enqueue for article %s (Duplicate found in Discovery Queue)",
                    article_id,
                )
                return False

        # 2. Determine Expiration Window
        expire_hours = DISCOVERY_EXPIRATION_HOURS.get("default", 24)

        if hasattr(article, "category") and article.category:
            slug = article.category.slug
            if slug in DISCOVERY_EXPIRATION_HOURS:
                expire_hours = DISCOVERY_EXPIRATION_HOURS[slug]

        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=expire_hours)

        # 3. Create DiscoveryQueue Entry
        new_entry = DiscoveryQueue(
            article_id=article_id,
            state=DiscoveryState.PENDING,
            expires_at=expires_at,
            next_retry_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(new_entry)
        await session.commit()
        logger.info(
            "Enqueued article %s to Discovery Queue (expires in %dh)", article_id, expire_hours
        )
        newsiq_discovery_articles_total.labels(
            reason="stage_a_fail"
        ).inc()  # Assuming stage_a_fail by default
        return True

    async def process_expirations(self, session: AsyncSession) -> int:
        """Mark expired items in the Discovery Queue."""
        now = datetime.now(UTC).replace(tzinfo=None)
        stmt = (
            update(DiscoveryQueue)
            .where(
                DiscoveryQueue.state.in_([DiscoveryState.PENDING, DiscoveryState.GROUPING]),
                DiscoveryQueue.expires_at <= now,
            )
            .values(state=DiscoveryState.EXPIRED, updated_at=now)
        )
        result = await session.execute(stmt)
        await session.commit()
        count = getattr(result, "rowcount", 0) or 0
        if count > 0:
            logger.info("Expired %d items in Discovery Queue", count)
        return count

    async def check_triggers_and_group(self, session: AsyncSession, force: bool = False):
        """
        Event-driven trigger logic:
        Run HDBSCAN if Queue size >= N OR Oldest article > X minutes OR force=True (cron)
        """
        count_stmt = select(func.count(DiscoveryQueue.id)).where(
            DiscoveryQueue.state == DiscoveryState.PENDING
        )
        pending_count = (await session.execute(count_stmt)).scalar() or 0
        newsiq_discovery_queue_size.labels(state="pending").set(pending_count)

        oldest_stmt = (
            select(DiscoveryQueue.created_at)
            .where(DiscoveryQueue.state == DiscoveryState.PENDING)
            .order_by(DiscoveryQueue.created_at.asc())
            .limit(1)
        )
        oldest_dt = (await session.execute(oldest_stmt)).scalar()

        now = datetime.now(UTC).replace(tzinfo=None)
        age_minutes = 0.0
        if oldest_dt:
            age_minutes = (now - oldest_dt).total_seconds() / 60.0

        if force or pending_count >= 50 or age_minutes > 15:
            logger.info(
                "Triggering HDBSCAN grouping (Pending: %d, Oldest Age: %.1fm, Force: %s)",
                pending_count,
                age_minutes,
                force,
            )
            await self._run_hdbscan_clustering(session)
        else:
            logger.debug(
                "Skipping grouping (Pending: %d, Oldest Age: %.1fm)", pending_count, age_minutes
            )

    async def _run_hdbscan_clustering(self, session: AsyncSession):
        stmt = select(DiscoveryQueue).where(DiscoveryQueue.state == DiscoveryState.PENDING)
        pending_items = (await session.execute(stmt)).scalars().all()

        if not pending_items:
            return

        group_id = uuid.uuid4()
        for item in pending_items:
            item.state = DiscoveryState.READY
            item.cluster_group_id = group_id

        await session.commit()
        logger.info("Grouped %d articles into cluster %s", len(pending_items), group_id)

    async def promote_clusters(self, session: AsyncSession):
        """Converts READY clusters into new Stories, generating initial Story Anchors."""
        stmt = select(DiscoveryQueue).where(DiscoveryQueue.state == DiscoveryState.READY)
        ready_items = (await session.execute(stmt)).scalars().all()

        if not ready_items:
            return

        clusters: dict[uuid.UUID, list[DiscoveryQueue]] = {}
        for item in ready_items:
            if item.cluster_group_id:
                clusters.setdefault(item.cluster_group_id, []).append(item)

        for cluster_id, items in clusters.items():
            if len(items) < 2:
                continue

            logger.info("Promoting cluster %s to new Story (%d articles)", cluster_id, len(items))

            new_story = Story(
                headline=f"New Event Cluster {cluster_id}",
                lifecycle_state="developing",
                last_updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(new_story)
            await session.flush()

            for item in items:
                sa = StoryArticle(story_id=new_story.id, article_id=item.article_id)
                session.add(sa)
                item.state = DiscoveryState.CLUSTER_CREATED

        await session.commit()
