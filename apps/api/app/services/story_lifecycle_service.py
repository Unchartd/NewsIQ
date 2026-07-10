"""Story Lifecycle Service

Manages state transitions for stories using the LifecycleRulesEngine and publishes events.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_publisher import StoryLifecycleChanged, event_publisher
from app.models.models import Story, StoryLifecycleState
from app.services.event_identity_service import event_identity_service
from app.services.lifecycle_rules import LifecycleRulesEngine

logger = logging.getLogger(__name__)


class StoryLifecycleManager:
    """Manages the state transitions and versioning for Stories."""

    def __init__(self, rules_engine: LifecycleRulesEngine | None = None):
        self.rules_engine = rules_engine or LifecycleRulesEngine()

    async def evaluate_and_transition(self, db: AsyncSession, story: Story) -> bool:
        """
        Evaluates a story using the RulesEngine and transitions it if thresholds are met.
        Returns True if a transition occurred, False otherwise.
        """
        decision = self.rules_engine.evaluate(story)
        if decision.should_transition:
            return await self._execute_transition(db, story, decision.target_state, decision.reason)
        return False

    async def manual_override(
        self, db: AsyncSession, story: Story, target_state: StoryLifecycleState, reason: str
    ) -> bool:
        """
        Allows administrators to manually override a story's lifecycle state.
        """
        reason = f"Manual Override: {reason}"
        return await self._execute_transition(db, story, target_state, reason)

    async def _execute_transition(
        self, db: AsyncSession, story: Story, target_state: StoryLifecycleState, reason: str
    ) -> bool:
        """
        Performs the state transition, updates DB fields, bumps version, and publishes an event.
        """
        if story.lifecycle_state == target_state:
            return False

        old_state = story.lifecycle_state
        now = datetime.now(UTC)

        # Update fields
        story.lifecycle_state = target_state
        story.transition_reason = reason
        story.lifecycle_changed_at = now

        # Phase B3: Canonical Event ID graduation
        if target_state in (StoryLifecycleState.MONITORING, StoryLifecycleState.STABLE):
            if not story.canonical_event_id or story.canonical_event_id.startswith("tmp_evt_"):
                story.canonical_event_id = event_identity_service.generate_canonical_id()
                if story.headline:
                    story.canonical_event_slug = event_identity_service.generate_display_slug(
                        story.headline, now.year
                    )
                logger.info(
                    "Assigned canonical ID %s to Story %s", story.canonical_event_id, story.id
                )

        # Only bump version on meaningful state change or content update.
        story.version += 1

        if target_state == StoryLifecycleState.ARCHIVED:
            story.archived_at = now

        db.add(story)
        await db.flush()

        logger.info(
            f"Story {story.id} transitioned from {old_state} to {target_state}. Reason: {reason}"
        )

        # Construct and publish strongly typed domain event
        health_metrics = {
            "confidence_score": story.confidence_score,
            "freshness_score": story.freshness_score,
            "source_diversity_count": story.source_diversity_count,
            "contradiction_score": story.contradiction_score,
        }

        event = StoryLifecycleChanged(
            story_id=story.id,
            canonical_event_id=story.canonical_event_id,
            old_state=old_state,
            new_state=target_state,
            reason=reason,
            story_version=story.version,
            health_metrics=health_metrics,
        )

        # In a transactional outbox pattern, we would save this to the DB first.
        # For now, we publish immediately to the abstract EventPublisher.
        event_publisher.publish("story.lifecycle.changed", event)

        # Basic observability metric logging
        # (In a real implementation, this would push to Prometheus/StatsD)
        logger.info(
            f'METRIC: lifecycle_transition_count{{from="{old_state}", to="{target_state}"}} 1'
        )

        return True


story_lifecycle_service = StoryLifecycleManager()
