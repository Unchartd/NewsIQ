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
from app.services.ai_service import StorySummaryResponse
from app.services.clustering_service import clustering_service
from app.services.contradiction_service import contradiction_service
from app.services.source_comparison_service import source_comparison_service


@pytest.mark.asyncio
@patch("app.services.ai_service.ai_service.summarize_story_from_kg")
@patch("app.services.ner_service_v2.ner_service_v2.extract_entities")
async def test_update_story_incrementally_flow(
    mock_extract_entities, mock_summarize_kg, mock_db_session
):
    """Verify that update_story_incrementally appends new events and calls summary generator."""
    story = Story(id=uuid.uuid4(), story_status="active", headline="Initial headline")

    src1 = Source(id=uuid.uuid4(), name="Reuters", country_code="US")
    art1 = Article(id=uuid.uuid4(), source_id=src1.id, title="Initial Article")
    art1.source = src1

    src2 = Source(id=uuid.uuid4(), name="BBC", country_code="GB")
    art2 = Article(id=uuid.uuid4(), source_id=src2.id, title="New Article")
    art2.source = src2

    # Events
    evt = ArticleEvent(
        article_id=art2.id,
        event_type="PROTEST",
        event_type_canonical="PROTEST",
        actors=["Activists"],
        targets=["Government"],
        location="London",
        event_time=datetime.datetime(2026, 6, 25, 12, 0, 0),
    )

    # Mock DB query results
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.scalar.return_value = None

        params = {}
        try:
            params = stmt.compile().params
        except Exception:
            pass

        if "from sources" in stmt_str:
            if any(str(src2.id) == str(v) for v in params.values()):
                res.scalar_one_or_none.return_value = src2
            else:
                res.scalar_one_or_none.return_value = src1
        elif "from article_events" in stmt_str:
            res.scalars.return_value.all.return_value = [evt]
        elif "story_entity" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "story_tag" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "story_timeline_event" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "story_difference" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "story_source_coverage" in stmt_str:
            res.scalars.return_value.all.return_value = []
        return res

    mock_db_session.execute.side_effect = mock_execute
    mock_extract_entities.return_value = []

    mock_summary_res = StorySummaryResponse(
        headline="Updated Incremental Headline",
        one_line_summary="Objective one line",
        short_summary="Objective short summary",
        detailed_summary="Objective detailed summary",
        key_facts=["Fact A"],
        category="world",
    )
    mock_summarize_kg.return_value = mock_summary_res

    # Mock dependencies
    with (
        patch.object(
            contradiction_service,
            "detect_and_save_contradictions_incremental",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            source_comparison_service, "compare_sources_and_save", AsyncMock(return_value=([], []))
        ),
        patch.object(clustering_service, "_index_and_invalidate", AsyncMock()),
    ):
        await clustering_service.update_story_incrementally(story, art2, [art1], mock_db_session)

        # Verify story fields updated
        assert story.headline == "Updated Incremental Headline"
        assert story.location_country == "GB"

        # Verify new timeline event was added
        added_objects = [args[0] for args, _ in mock_db_session.add.call_args_list]
        timeline_events = [obj for obj in added_objects if isinstance(obj, StoryTimelineEvent)]
        assert len(timeline_events) == 1
        assert "Protest reported by BBC" in timeline_events[0].description
