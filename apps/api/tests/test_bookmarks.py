"""Unit tests for the story bookmarking endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.stories import bookmark_story, unbookmark_story
from app.models.models import Bookmark, Story, StoryMetric, User


@pytest.mark.asyncio
@patch("app.api.v1.stories.cache_service")
async def test_bookmark_story_success(mock_cache_service, mock_db_session):
    """Verify bookmark_story records user event, updates metrics, and invalidates cache."""
    user = User(id=uuid.uuid4())
    story_id = uuid.uuid4()
    story = Story(id=story_id, metrics=StoryMetric(story_id=story_id, bookmarks=0))

    # Mock DB executions
    # 1. Select story
    # 2. Select bookmark
    mock_res_story = MagicMock()
    mock_res_story.scalar_one_or_none.return_value = story

    mock_res_bm = MagicMock()
    mock_res_bm.scalar_one_or_none.return_value = None  # Not bookmarked yet

    mock_db_session.execute.side_effect = [mock_res_story, mock_res_bm]

    mock_cache_service.invalidate_story = AsyncMock()

    response = await bookmark_story(story_id=story_id, current_user=user, db=mock_db_session)

    assert response == {"message": "Story bookmarked successfully."}
    assert story.metrics.bookmarks == 1
    assert mock_db_session.add.call_count == 2  # Bookmark and UserEvent
    mock_db_session.commit.assert_called_once()
    mock_cache_service.invalidate_story.assert_called_once_with(str(story_id))


@pytest.mark.asyncio
@patch("app.api.v1.stories.cache_service")
async def test_bookmark_story_already_bookmarked(mock_cache_service, mock_db_session):
    """Verify bookmark_story returns early if already bookmarked."""
    user = User(id=uuid.uuid4())
    story_id = uuid.uuid4()
    story = Story(id=story_id)

    mock_res_story = MagicMock()
    mock_res_story.scalar_one_or_none.return_value = story

    mock_res_bm = MagicMock()
    mock_res_bm.scalar_one_or_none.return_value = Bookmark(user_id=user.id, story_id=story_id)

    mock_db_session.execute.side_effect = [mock_res_story, mock_res_bm]

    mock_cache_service.invalidate_story = AsyncMock()

    response = await bookmark_story(story_id=story_id, current_user=user, db=mock_db_session)

    assert response == {"message": "Already bookmarked."}
    mock_db_session.add.assert_not_called()
    mock_cache_service.invalidate_story.assert_not_called()


@pytest.mark.asyncio
@patch("app.api.v1.stories.cache_service")
async def test_unbookmark_story_success(mock_cache_service, mock_db_session):
    """Verify unbookmark_story deletes bookmark, decrements metrics, and invalidates cache."""
    user = User(id=uuid.uuid4())
    story_id = uuid.uuid4()
    bookmark = Bookmark(user_id=user.id, story_id=story_id)
    story = Story(id=story_id, metrics=StoryMetric(story_id=story_id, bookmarks=1))

    # Mock DB executions
    # 1. Select bookmark
    # 2. Select story
    mock_res_bm = MagicMock()
    mock_res_bm.scalar_one_or_none.return_value = bookmark

    mock_res_story = MagicMock()
    mock_res_story.scalar_one_or_none.return_value = story

    mock_db_session.execute.side_effect = [mock_res_bm, mock_res_story]

    mock_cache_service.invalidate_story = AsyncMock()

    response = await unbookmark_story(story_id=story_id, current_user=user, db=mock_db_session)

    assert response == {"message": "Bookmark removed successfully."}
    assert story.metrics.bookmarks == 0
    mock_db_session.delete.assert_called_once_with(bookmark)
    mock_db_session.commit.assert_called_once()
    mock_cache_service.invalidate_story.assert_called_once_with(str(story_id))


@pytest.mark.asyncio
@patch("app.api.v1.stories.cache_service")
async def test_unbookmark_story_not_found(mock_cache_service, mock_db_session):
    """Verify unbookmark_story raises 404 when bookmark is not found."""
    user = User(id=uuid.uuid4())
    story_id = uuid.uuid4()

    mock_res_bm = MagicMock()
    mock_res_bm.scalar_one_or_none.return_value = None

    mock_db_session.execute.return_value = mock_res_bm

    mock_cache_service.invalidate_story = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await unbookmark_story(story_id=story_id, current_user=user, db=mock_db_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Bookmark not found."
    mock_db_session.delete.assert_not_called()
    mock_cache_service.invalidate_story.assert_not_called()
