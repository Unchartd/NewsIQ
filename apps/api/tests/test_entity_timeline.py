"""Unit tests for the entity timeline endpoint."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.stories import get_entity_timeline
from app.models.models import CanonicalEntity, Story, StoryMetric


@pytest.mark.asyncio
async def test_get_entity_timeline_not_found(mock_db_session):
    """Verify get_entity_timeline raises 404 when Canonical Entity is not found."""
    entity_id = uuid.uuid4()

    mock_res_ent = MagicMock()
    mock_res_ent.scalar_one_or_none.return_value = None

    mock_db_session.execute.return_value = mock_res_ent

    with pytest.raises(HTTPException) as exc_info:
        await get_entity_timeline(
            canonical_entity_id=entity_id, limit=20, offset=0, db=mock_db_session
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Canonical Entity not found."


@pytest.mark.asyncio
async def test_get_entity_timeline_success(mock_db_session):
    """Verify get_entity_timeline returns stories linked to the entity."""
    entity_id = uuid.uuid4()
    entity = CanonicalEntity(id=entity_id, canonical_name="Test Entity", entity_type="ORG")

    story_id = uuid.uuid4()
    story = Story(
        id=story_id,
        headline="Test Headline",
        one_line_summary="Test Summary",
        category=None,
        articles=[],
        trend_score=0.5,
    )

    mock_res_ent = MagicMock()
    mock_res_ent.scalar_one_or_none.return_value = entity

    mock_res_stories = MagicMock()
    mock_res_stories.scalars.return_value.all.return_value = [story]

    mock_db_session.execute.side_effect = [mock_res_ent, mock_res_stories]

    response = await get_entity_timeline(
        canonical_entity_id=entity_id, limit=20, offset=0, db=mock_db_session
    )

    assert len(response) == 1
    assert response[0].id == story_id
    assert response[0].headline == "Test Headline"
