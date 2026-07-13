import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import Article, Story
from app.services.clustering_service import clustering_service


@pytest.mark.asyncio
@patch("app.services.ai_service.ai_service.summarize_story_from_kg")
@patch("app.services.ner_service_v2.ner_service_v2.extract_entities")
@patch("app.core.database.get_db")
async def test_incremental_updates_guard(mock_get_db, mock_extract_entities, mock_summarize_kg, mock_db_session):
    mock_get_db.return_value = mock_db_session

    story = Story(id=uuid.uuid4(), headline="Original Headline")
    art = Article(id=uuid.uuid4(), title="Article Title", content="Article Content")

    # Mock DB query results
    mock_db_session.execute = AsyncMock()
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = MagicMock(id=uuid.uuid4())
    mock_db_session.execute.return_value = mock_scalar

    # Mock other services called inside pipeline
    mock_extract_entities.return_value = []
    mock_summarize_kg.return_value = MagicMock(
        headline="New Headline",
        one_line_summary="One line",
        short_summary="Short",
        detailed_summary="Detailed",
        key_facts=["Fact"],
        category="world",
    )

    from app.services.cache_service import cache_service
    from app.services.contradiction_service import contradiction_service
    from app.services.pipeline_cache import pipeline_cache
    from app.services.source_comparison_service import source_comparison_service

    mock_detect = AsyncMock(return_value=[])
    mock_compare = AsyncMock(return_value=(([], [])))

    # Enable cache and mock Redis via public API methods
    pipeline_cache._is_enabled = MagicMock(return_value=True)

    stored_hashes = {}
    async def mock_get_raw(key):
        return stored_hashes.get(key)
    async def mock_set_raw(key, val, ttl=None):
        stored_hashes[key] = val

    async def mock_get_stage_result(stage, content_hash, *args, **kwargs):
        key = f"stage:{stage}:{content_hash}"
        return stored_hashes.get(key)
    async def mock_set_stage_result(stage, content_hash, result_data, *args, **kwargs):
        key = f"stage:{stage}:{content_hash}"
        stored_hashes[key] = result_data

    async def mock_pipeline_get(stage, model, prompt_version, content_hash, *args, **kwargs):
        key = f"pipeline:{stage}:{content_hash}"
        return stored_hashes.get(key)
    async def mock_pipeline_set(stage, model, prompt_version, content_hash, result_data, *args, **kwargs):
        key = f"pipeline:{stage}:{content_hash}"
        stored_hashes[key] = result_data

    with (
        patch.object(cache_service, "get_raw", mock_get_raw),
        patch.object(cache_service, "set_raw", mock_set_raw),
        patch.object(pipeline_cache, "get_stage_result", mock_get_stage_result),
        patch.object(pipeline_cache, "set_stage_result", mock_set_stage_result),
        patch.object(pipeline_cache, "get", mock_pipeline_get),
        patch.object(pipeline_cache, "set", mock_pipeline_set),
        patch.object(contradiction_service, "detect_and_save_contradictions", mock_detect),
        patch.object(source_comparison_service, "compare_sources_and_save", mock_compare),
        patch.object(clustering_service, "_index_and_invalidate", AsyncMock()),
    ):
        # 1. Run first time: Guard Misses (since no cache entry)
        await clustering_service.generate_story_content(story, [art], mock_db_session)
        assert mock_detect.call_count == 1
        assert mock_compare.call_count == 1

        # Check that simulated cache has the guard key
        guard_key = f"story_synthesis_hash:{story.id}"
        assert guard_key in stored_hashes

        # Reset counts
        mock_detect.reset_mock()
        mock_compare.reset_mock()

        # 2. Run second time: Guard Hits (skips entire function)
        await clustering_service.generate_story_content(story, [art], mock_db_session)
        assert mock_detect.call_count == 0
        assert mock_compare.call_count == 0

        # 3. Modify headline to None: Guard is bypassed (must regenerate)
        story.headline = None
        stored_hashes.clear()
        await clustering_service.generate_story_content(story, [art], mock_db_session)
        assert mock_detect.call_count == 1
        assert mock_compare.call_count == 1
