"""Unit tests for Batch 5 Synthesis & Validation: KG-grounded summarization and integration."""

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import (
    Article,
    ArticleEvent,
    Source,
    Story,
    StoryTimelineEvent,
)
from app.services.ai_service import StorySummaryResponse, ai_service
from app.services.clustering_service import clustering_service
from app.services.contradiction_service import contradiction_service
from app.services.source_comparison_service import source_comparison_service


@pytest.mark.asyncio
async def test_build_summary_prompt():
    """Verify that the summary prompt builder correctly serializes input structures."""
    kg = {
        "nodes": [{"id": "event_1", "label": "PROTEST", "type": "event"}],
        "edges": [],
    }
    contradictions = [
        {
            "fact_type": "number",
            "description": "Conflict on casualties.",
            "confidence": 0.95,
        }
    ]
    timeline = [{"date": "2026-06-20", "description": "Protest happened"}]
    source_comparisons = [
        {
            "source_name": "BBC",
            "focus_area": "Detailed protest coverage",
            "unique_information": "Unique local quotes",
        }
    ]

    prompt = ai_service._build_summary_prompt(kg, contradictions, timeline, source_comparisons)

    # Check that all components are embedded in the prompt
    assert "PROTEST" in prompt
    assert "Conflict on casualties" in prompt
    assert "2026-06-20" in prompt
    assert "Unique local quotes" in prompt
    assert "StorySummaryResponse" not in prompt  # check format


@pytest.mark.asyncio
async def test_summarize_story_from_kg_mock_fallback():
    """Verify that summarize_story_from_kg falls back to deterministic mock when AI is disabled."""
    ai_service.gemini_enabled = False
    ai_service.openai_enabled = False

    kg = {
        "nodes": [
            {"id": "event_1", "label": "PROTEST", "type": "event", "properties": {"event_time_raw": "2026-06-20"}},
            {"id": "entity_1", "label": "Actor A", "type": "entity"},
            {"id": "source_1", "label": "BBC", "type": "source"},
        ],
        "edges": [],
    }

    with patch("app.llm_gateway.fallback_chain.FallbackChain.get_fallback_chain") as mock_chain:
        mock_chain.return_value = [{"provider": "mock", "model": "mock"}]
        res = await ai_service.summarize_story_from_kg(kg, [], [], [])

    assert "protest" in res.headline.lower()
    assert "world" == res.category
    assert len(res.key_facts) > 0


@pytest.mark.asyncio
@patch("app.services.ai_service.ai_service.summarize_story_from_kg")
@patch("app.services.ner_service_v2.ner_service_v2.extract_entities")
async def test_generate_story_content_end_to_end_synthesis(
    mock_extract_entities, mock_summarize_kg, mock_db_session
):
    """Verify that generate_story_content runs the entire reordered pipeline and saves the summary."""
    story_id = uuid.uuid4()
    story = Story(id=story_id)

    src_id = uuid.uuid4()
    src = Source(id=src_id, name="Reuters")

    art = Article(id=uuid.uuid4(), source_id=src_id, title="Incident Report")
    art.source = src

    # Event
    evt = ArticleEvent(
        article_id=art.id,
        event_type="ATTACK",
        event_type_canonical="ATTACK",
        actors=["Rebels"],
        targets=["Town"],
        location="Frontline",
        event_time=datetime.datetime(2026, 6, 20, 10, 0, 0),
    )

    # Mock DB query results
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.scalar.return_value = None
        if "from sources" in stmt_str:
            res.scalar_one_or_none.return_value = src
        elif "from article_events" in stmt_str:
            res.scalars.return_value.all.return_value = [evt]
        return res

    mock_db_session.execute.side_effect = mock_execute

    # Mock NER entities
    mock_extract_entities.return_value = []

    # Mock synthesis result
    mock_summary_res = StorySummaryResponse(
        headline="Validated Event Headline",
        one_line_summary="Objective one line",
        short_summary="Objective short summary",
        detailed_summary="Objective detailed summary",
        key_facts=["Fact A", "Fact B"],
        category="science",
    )
    mock_summarize_kg.return_value = mock_summary_res

    # Mock dependencies
    with patch.object(contradiction_service, "detect_and_save_contradictions", AsyncMock(return_value=[])), \
         patch.object(source_comparison_service, "compare_sources_and_save", AsyncMock(return_value=([], []))), \
         patch.object(clustering_service, "_index_and_invalidate", AsyncMock()) as mock_index:

        await clustering_service.generate_story_content(story, [art], mock_db_session)

        # 1. Verify story summaries got updated with mock_summary_res
        assert story.headline == "Validated Event Headline"
        assert story.one_line_summary == "Objective one line"
        assert story.category_id is not None  # mapped science category

        # 2. Verify timeline objects were added
        added_objects = [args[0] for args, _ in mock_db_session.add.call_args_list]
        timeline_events = [obj for obj in added_objects if isinstance(obj, StoryTimelineEvent)]
        assert len(timeline_events) == 1
        assert "Attack reported by Reuters" in timeline_events[0].description

        # 3. Verify Meilisearch index call was triggered
        mock_index.assert_called_once()
