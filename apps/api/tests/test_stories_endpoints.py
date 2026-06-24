"""Unit tests for news stories endpoints, focusing on dynamic similarity calculations."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.stories import list_stories
from app.models.models import ArticleEvent, Story


@pytest.mark.asyncio
async def test_list_stories_with_cluster_confidence(mock_db_session):
    """Verify list_stories computes and returns dynamic cluster confidence scores."""
    story_id = uuid.uuid4()
    story = Story(
        id=story_id,
        headline="AI Breakthrough",
        one_line_summary="A short summary",
        trend_score=1.5,
        first_seen_at=None,
        updated_at=None,
        category=None,
        articles=[],
    )

    mock_res_stories = MagicMock()
    mock_res_stories.scalars.return_value.all.return_value = [story]

    event1 = ArticleEvent(
        id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        event_type="test",
        actors=["US"],
        targets=["China"],
        location="US",
        event_time=None,
    )
    event2 = ArticleEvent(
        id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        event_type="test",
        actors=["US"],
        targets=["China"],
        location="US",
        event_time=None,
    )

    mock_res_events = MagicMock()
    mock_res_events.all.return_value = [
        (event1, story_id),
        (event2, story_id),
    ]

    mock_db_session.execute.side_effect = [mock_res_stories, mock_res_events]

    with patch(
        "app.services.clustering_service.clustering_service._compute_event_similarity_direct",
        return_value=0.85,
    ) as mock_sim:
        responses = await list_stories(q=None, status=None, limit=20, offset=0, db=mock_db_session)

        assert len(responses) == 1
        assert responses[0].id == story_id
        assert responses[0].cluster_confidence == 0.85
        mock_sim.assert_called_once_with(event1, event2)
