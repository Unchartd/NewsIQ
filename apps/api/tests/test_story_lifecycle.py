from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.models import Story, StoryLifecycleState
from app.services.lifecycle_rules import LifecycleRulesEngine
from app.services.story_lifecycle_service import StoryLifecycleManager


@pytest.fixture
def rules_engine():
    # Use fallback default config
    engine = LifecycleRulesEngine()
    return engine


@pytest.fixture
def lifecycle_manager(rules_engine):
    return StoryLifecycleManager(rules_engine=rules_engine)


def test_evaluate_emerging_to_developing(rules_engine):
    story = Story(
        lifecycle_state=StoryLifecycleState.EMERGING,
        source_diversity_count=3,
        articles=[] # relationship cannot be mocked with ints
    )
    decision = rules_engine.evaluate(story)
    assert decision.should_transition is True
    assert decision.target_state == StoryLifecycleState.DEVELOPING


def test_evaluate_developing_to_monitoring(rules_engine):
    last_update = datetime.now(UTC) - timedelta(hours=7)
    story = Story(
        lifecycle_state=StoryLifecycleState.DEVELOPING,
        confidence_score=0.85,
        source_diversity_count=4,
        contradiction_score=0.1,
        last_significant_update_at=last_update
    )
    decision = rules_engine.evaluate(story)
    assert decision.should_transition is True
    assert decision.target_state == StoryLifecycleState.MONITORING


def test_evaluate_monitoring_to_stable(rules_engine):
    last_update = datetime.now(UTC) - timedelta(hours=25)
    story = Story(
        lifecycle_state=StoryLifecycleState.MONITORING,
        confidence_score=0.96,
        source_diversity_count=6,
        contradiction_score=0.05,
        last_significant_update_at=last_update
    )
    decision = rules_engine.evaluate(story)
    assert decision.should_transition is True
    assert decision.target_state == StoryLifecycleState.STABLE


def test_evaluate_stable_to_archived(rules_engine):
    last_update = datetime.now(UTC) - timedelta(hours=200)
    story = Story(
        lifecycle_state=StoryLifecycleState.STABLE,
        last_significant_update_at=last_update,
        last_discovery_at=last_update
    )
    decision = rules_engine.evaluate(story)
    assert decision.should_transition is True
    assert decision.target_state == StoryLifecycleState.ARCHIVED


@pytest.mark.asyncio
async def test_manual_override(lifecycle_manager):
    story = Story(
        id="123e4567-e89b-12d3-a456-426614174000",
        lifecycle_state=StoryLifecycleState.DEVELOPING,
        version=1,
        confidence_score=0.9
    )
    db_session = AsyncMock()

    transitioned = await lifecycle_manager.manual_override(
        db_session, story, StoryLifecycleState.STABLE, "Admin action"
    )

    assert transitioned is True
    assert story.lifecycle_state == StoryLifecycleState.STABLE
    assert story.version == 2
    assert "Manual Override" in story.transition_reason
    db_session.add.assert_called_once_with(story)
    db_session.flush.assert_called_once()
