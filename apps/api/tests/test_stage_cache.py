import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import (
    Article,
    Source,
    Story,
)
from app.services.clustering_service import clustering_service
from app.services.pipeline_cache import pipeline_cache


@pytest.mark.asyncio
@patch("app.services.ai_service.ai_service.summarize_story_from_kg")
@patch("app.services.ner_service_v2.ner_service_v2.extract_entities")
async def test_stage_level_caching_flow(mock_extract_entities, mock_summarize_kg, mock_db_session):
    """Verify that stage-level caching intercepts contradiction and source comparison stages."""
    story = Story(id=uuid.uuid4())
    src = Source(id=uuid.uuid4(), name="Bloomberg")
    art = Article(id=uuid.uuid4(), source_id=src.id, title="Market Peak")
    art.source = src

    # Mock DB query results
    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = src
        res.scalar_one.return_value = 0
        res.scalar.return_value = None
        res.scalars.return_value.all.return_value = []
        return res

    mock_db_session.execute.side_effect = mock_execute
    mock_extract_entities.return_value = []
    mock_summarize_kg.return_value = MagicMock(
        headline="Market Peak",
        one_line_summary="World summary",
        short_summary="Short",
        detailed_summary="Detailed",
        key_facts=["Fact 1"],
        category="business",
    )

    from app.services.contradiction_service import contradiction_service
    from app.services.source_comparison_service import source_comparison_service

    # Setup Mocks
    mock_detect = AsyncMock(return_value=[])
    mock_compare = AsyncMock(return_value=([], []))

    # Enable cache
    pipeline_cache._is_enabled = MagicMock(return_value=True)

    cache_store = {}

    async def mock_get(key):
        return cache_store.get(key)

    async def mock_set(key, value, ttl=None):
        import copy

        cache_store[key] = copy.deepcopy(value)

    async def mock_delete(*keys):
        for k in keys:
            cache_store.pop(k, None)

    with (
        patch("app.services.cache_service.cache_service.get", side_effect=mock_get),
        patch("app.services.cache_service.cache_service.set", side_effect=mock_set),
        patch("app.services.cache_service.cache_service.delete", side_effect=mock_delete),
        patch.object(contradiction_service, "detect_and_save_contradictions", mock_detect),
        patch.object(source_comparison_service, "compare_sources_and_save", mock_compare),
        patch.object(clustering_service, "_index_and_invalidate", AsyncMock()),
        patch(
            "app.services.story_synthesis_service.evaluate_story_quality",
            AsyncMock(
                return_value=MagicMock(
                    action="publish",
                    score=1.0,
                    explanation="Passed mock",
                    hallucination_detected=False,
                )
            ),
        ),
    ):
        # Clear Redis keys first to ensure clean state
        article_inputs = [f"{art.id}:{art.title or ''}:{art.description or ''}"]
        story_input_hash = pipeline_cache.composite_hash(*article_inputs)
        pipeline_version = "1.0.0"

        from app.services.cache_service import cache_service

        await cache_service.delete(
            f"stage_cache:contradictions:{pipeline_version}:{story_input_hash}"
        )
        await cache_service.delete(
            f"stage_cache:source_comparison:{pipeline_version}:{story_input_hash}"
        )

        # ── Run 1: Cache Miss ──
        await clustering_service.generate_story_content(story, [art], mock_db_session)
        assert mock_detect.call_count == 1
        assert mock_compare.call_count == 1

        # Reset call counts
        mock_detect.reset_mock()
        mock_compare.reset_mock()

        # ── Run 2: Cache Hit ──
        await clustering_service.generate_story_content(story, [art], mock_db_session)
        assert mock_detect.call_count == 0
        assert mock_compare.call_count == 0
