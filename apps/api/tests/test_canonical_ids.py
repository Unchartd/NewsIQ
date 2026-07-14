import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.models import Story, StoryLifecycleState
from app.services.event_identity_service import EventIdentityService


def test_generate_temporary_id():
    service = EventIdentityService()
    tid = service.generate_temporary_id()

    assert tid.startswith("tmp_evt_")
    assert len(tid) > 10
    assert service.metrics["tmp_ids_created"] == 1


def test_generate_canonical_id():
    service = EventIdentityService()
    cid = service.generate_canonical_id()

    assert cid.startswith("evt_")
    assert len(cid) > 10
    assert service.metrics["canonical_ids_created"] == 1
    # Check it's base32
    assert "=" not in cid


def test_generate_display_slug():
    service = EventIdentityService()

    # Standard headline
    slug1 = service.generate_display_slug("Apple Launches AI Chip!", 2026)
    assert slug1 == "apple-launches-ai-chip-2026"

    # Lots of punctuation
    slug2 = service.generate_display_slug("Breaking: Market crashes 20% today?", 2026)
    assert slug2 == "breaking-market-crashes-20-today-2026"

    # Missing headline fallback
    slug3 = service.generate_display_slug("", 2026)
    assert slug3.startswith("event-")
    assert slug3.endswith("-2026")


@pytest.mark.asyncio
async def test_handle_merge_creates_alias():
    service = EventIdentityService()
    session_mock = AsyncMock()

    await service.handle_merge("evt_old", "evt_new", "Merged due to entity overlap", session_mock)

    assert service.metrics["aliases_created"] == 1
    assert service.metrics["merges_handled"] == 1
    session_mock.add.assert_called_once()

    # Don't alias temporary IDs
    session_mock.reset_mock()
    await service.handle_merge("tmp_evt_123", "evt_new", "Promoted", session_mock)
    session_mock.add.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.story_lifecycle_service.event_identity_service")
@patch("app.services.story_lifecycle_service.event_publisher.publish")
async def test_lifecycle_graduation(mock_publish, mock_identity):
    mock_identity.generate_canonical_id.return_value = "evt_abc123"
    mock_identity.generate_display_slug.return_value = "test-event-2026"

    from app.services.story_lifecycle_service import StoryLifecycleManager

    manager = StoryLifecycleManager()

    db_mock = AsyncMock()
    datetime.now(UTC)

    story = Story(
        id=uuid.uuid4(),
        lifecycle_state=StoryLifecycleState.DEVELOPING,
        canonical_event_id="tmp_evt_123",
        headline="Test Event",
        version=1,
    )

    # Transition to Monitoring
    await manager._execute_transition(
        db_mock, story, StoryLifecycleState.MONITORING, "Stable enough"
    )

    # Canonical ID should be assigned
    assert story.lifecycle_state == StoryLifecycleState.MONITORING
    assert story.canonical_event_id == "evt_abc123"
    assert story.canonical_event_slug == "test-event-2026"
    assert story.version == 2
    mock_identity.generate_canonical_id.assert_called_once()
    mock_identity.generate_display_slug.assert_called_once()
