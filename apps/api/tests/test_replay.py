"""Unit tests for the pipeline replay service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Article, Story, StoryArticle
from app.services.replay_service import replay_service


@pytest.mark.asyncio
async def test_replay_full_story():
    """Verify that replay_full_story fetches story data and calls generate_story_content."""
    story_id = uuid.uuid4()
    mock_db = MagicMock(spec=AsyncSession)

    # Mock story and article relationship
    mock_article = Article(id=uuid.uuid4(), title="Original Article")
    mock_sa = StoryArticle(article=mock_article)
    mock_story = Story(id=story_id, headline="Test Headline")
    mock_story.articles = [mock_sa]

    # Execute DB mocks
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_story
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.clustering_service.clustering_service.generate_story_content",
        AsyncMock(),
    ) as mock_generate:
        await replay_service.replay_full_story(story_id, mock_db)

        # Assertions
        mock_db.execute.assert_called_once()
        mock_generate.assert_called_once_with(mock_story, [mock_article], mock_db)


@pytest.mark.asyncio
async def test_replay_story_stage_contradictions():
    """Verify that replaying contradiction stage calls contradiction_service."""
    story_id = uuid.uuid4()
    mock_db = MagicMock(spec=AsyncSession)

    # Mock story
    mock_story = Story(id=story_id, headline="Test Headline")
    mock_story.articles = []  # No articles needed for this test path

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_story
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Make articles mock non-empty to bypass return check
    mock_article = Article(id=uuid.uuid4(), title="Original Article")
    mock_sa = StoryArticle(article=mock_article)
    mock_story.articles = [mock_sa]

    with patch(
        "app.services.contradiction_service.contradiction_service.detect_and_save_contradictions",
        AsyncMock(),
    ) as mock_contra:
        await replay_service.replay_story_stage(story_id, "contradiction_detection", mock_db)

        # Assertions
        mock_contra.assert_called_once_with(story_id, mock_db)
