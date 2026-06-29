"""Unit tests for Batch 4 Analysis Engines: contradictions, source coverage, and timelines."""

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import (
    Article,
    ArticleEvent,
    Source,
    Story,
    StoryContradiction,
    StoryTimelineEvent,
)
from app.services.clustering_service import clustering_service
from app.services.contradiction_service import ContradictionResolution, contradiction_service
from app.services.source_comparison_service import (
    SourceComparisonResolution,
    source_comparison_service,
)


@pytest.mark.asyncio
async def test_contradiction_heuristics_candidate_detection(mock_db_session):
    """Verify that contradiction heuristics accurately flag candidates."""
    story_id = uuid.uuid4()
    src1_id = uuid.uuid4()
    src2_id = uuid.uuid4()

    # 1. Setup articles and events with contradictory fields
    art1 = Article(id=uuid.uuid4(), source_id=src1_id, title="Report A")
    art2 = Article(id=uuid.uuid4(), source_id=src2_id, title="Report B")

    # Set up sources
    src1 = Source(id=src1_id, name="Publisher A")
    src2 = Source(id=src2_id, name="Publisher B")
    art1.source = src1
    art2.source = src2

    # Event 1: Actors "Russia", Targets "Ukraine", Location "Kyiv", Time 2026-06-20, Casualties 10
    evt1 = ArticleEvent(
        article_id=art1.id,
        actors=["Russia"],
        targets=["Ukraine"],
        location="Kyiv",
        event_time=datetime.datetime(2026, 6, 20, 10, 0, 0),
        numbers={"casualties": 10},
    )

    # Event 2: Actors "Ukraine" (disjoint actor), Targets "Russia" (disjoint target), Location "London" (different loc), Time 2026-06-25 (diff > 1 day), Casualties 50 (diff > 10% and > 1)
    evt2 = ArticleEvent(
        article_id=art2.id,
        actors=["Ukraine"],
        targets=["Russia"],
        location="London",
        event_time=datetime.datetime(2026, 6, 25, 10, 0, 0),
        numbers={"casualties": 50},
    )

    # Mock execute to return these pairs
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.scalar.return_value = None
        if "story_articles" in stmt_str:
            res.all.return_value = [(art1, evt1), (art2, evt2)]
        return res

    mock_db_session.execute.side_effect = mock_execute

    # Mock the LLM call to return true contradictions for all candidates
    mock_resolution = ContradictionResolution(
        is_contradiction=True,
        description="Factual conflict found",
        confidence=0.95,
    )

    with patch.object(
        contradiction_service, "_validate_with_llm", AsyncMock(return_value=mock_resolution)
    ):
        contradictions = await contradiction_service.detect_and_save_contradictions(
            story_id, mock_db_session
        )

        # We should find contradictions for: actor, target, location, event_time, number
        assert len(contradictions) == 5
        fact_types = {c.fact_type for c in contradictions}
        assert "actor" in fact_types
        assert "target" in fact_types
        assert "location" in fact_types
        assert "event_time" in fact_types
        assert "number" in fact_types

        # Verify DB add was called for each contradiction
        assert mock_db_session.add.call_count == 5


@pytest.mark.asyncio
async def test_contradiction_heuristics_non_conflict(mock_db_session):
    """Verify that matching fields do NOT trigger contradiction candidates."""
    story_id = uuid.uuid4()
    src1_id = uuid.uuid4()
    src2_id = uuid.uuid4()

    art1 = Article(id=uuid.uuid4(), source_id=src1_id, title="Report A")
    art2 = Article(id=uuid.uuid4(), source_id=src2_id, title="Report B")
    art1.source = Source(id=src1_id, name="Publisher A")
    art2.source = Source(id=src2_id, name="Publisher B")

    # Match all fields: overlapping actors, same location (substring), same time, similar casualties (< 10%)
    evt1 = ArticleEvent(
        article_id=art1.id,
        actors=["Russia", "Belarus"],
        targets=["Ukraine"],
        location="Kyiv Oblast",
        event_time=datetime.datetime(2026, 6, 20, 10, 0, 0),
        numbers={"casualties": 10},
    )
    evt2 = ArticleEvent(
        article_id=art2.id,
        actors=["Russia"],  # Intersects
        targets=["Ukraine"],  # Intersects
        location="Kyiv",  # Substring
        event_time=datetime.datetime(2026, 6, 20, 15, 0, 0),  # < 1 day diff
        numbers={"casualties": 10},  # Same
    )

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.all.return_value = [(art1, evt1), (art2, evt2)]
        return res

    mock_db_session.execute.side_effect = mock_execute

    contradictions = await contradiction_service.detect_and_save_contradictions(
        story_id, mock_db_session
    )
    # Zero candidates should be flagged
    assert len(contradictions) == 0
    assert mock_db_session.add.call_count == 0


@pytest.mark.asyncio
async def test_source_comparison_heuristics_and_llm(mock_db_session):
    """Verify that source comparison detects unique/missing facts and runs LLM synthesis."""
    story_id = uuid.uuid4()
    src1_id = uuid.uuid4()
    src2_id = uuid.uuid4()

    # Create sources
    src1 = Source(id=src1_id, name="BBC")
    src2 = Source(id=src2_id, name="Reuters")

    # Setup articles
    art1 = Article(id=uuid.uuid4(), source_id=src1_id, title="BBC Report")
    art2 = Article(id=uuid.uuid4(), source_id=src2_id, title="Reuters Report")
    art1.source = src1
    art2.source = src2

    # Event 1: BBC reports actor "Actor A" and number "casualties: 10"
    evt1 = ArticleEvent(
        article_id=art1.id,
        event_type="PROTEST",
        event_type_canonical="PROTEST",
        actors=["Actor A"],
        targets=["Target A"],
        location="Location A",
        numbers={"casualties": 10},
    )

    # Event 2: Reuters reports actor "Actor B" and target "Target B"
    evt2 = ArticleEvent(
        article_id=art2.id,
        event_type="PROTEST",
        event_type_canonical="PROTEST",
        actors=["Actor B"],
        targets=["Target B"],
        location="Location B",
        numbers={"casualties": 50},
    )

    # Setup mocked DB session returns
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.scalar.return_value = None
        if "from articles" in stmt_str or "story_articles" in stmt_str:
            res.all.return_value = [(art1, src1), (art2, src2)]
        elif "from article_events" in stmt_str:
            res.scalars.return_value.all.return_value = [evt1, evt2]
        elif "from story_contradictions" in stmt_str:
            # Mock a contradiction
            c = StoryContradiction(
                story_id=story_id,
                fact_type="number",
                description="BBC reports casualties: 10, Reuters reports casualties: 50",
                source_attribution={str(src1_id): "10", str(src2_id): "50"},
            )
            res.scalars.return_value.all.return_value = [c]
        return res

    mock_db_session.execute.side_effect = mock_execute

    # Mock the LLM response
    mock_resolution_bbc = SourceComparisonResolution(
        focus_area="Protest coverage focusing on Actor A.",
        unique_information="Reports Actor A specifically.",
        missing_information="Omitted Actor B and Target B.",
        contradictions="Contradicts Reuters on casualties.",
    )
    mock_resolution_reuters = SourceComparisonResolution(
        focus_area="Protest coverage focusing on Actor B.",
        unique_information="Reports Actor B and Target B specifically.",
        missing_information="Omitted Actor A.",
        contradictions="Contradicts BBC on casualties.",
    )

    async def mock_analyze_llm(src_name, unique_summary, missing_summary, contradictions_summary, context):
        if "bbc" in src_name.lower():
            # Validate that unique summary for BBC contains Actor A
            assert "actor a" in unique_summary.lower()
            assert "actor b" in missing_summary.lower()
            return mock_resolution_bbc
        else:
            assert "actor b" in unique_summary.lower()
            assert "actor a" in missing_summary.lower()
            return mock_resolution_reuters

    with patch.object(
        source_comparison_service, "_analyze_with_llm", side_effect=mock_analyze_llm
    ):
        coverages, differences = await source_comparison_service.compare_sources_and_save(
            story_id, mock_db_session
        )

        assert len(coverages) == 2
        assert len(differences) == 2

        bbc_coverage = next(c for c in coverages if c.source_id == src1_id)
        assert bbc_coverage.focus_area == "Protest coverage focusing on Actor A."

        bbc_diff = next(d for d in differences if d.source_id == src1_id)
        assert bbc_diff.unique_information == "Reports Actor A specifically."
        assert bbc_diff.missing_information == "Omitted Actor B and Target B."
        assert bbc_diff.contradictions == "Contradicts Reuters on casualties."


@pytest.mark.asyncio
async def test_source_comparison_deterministic_fallback():
    """Verify that deterministic fallback triggers when LLM is disabled."""
    # Ensure LLM clients are disabled
    source_comparison_service.gemini_enabled = False
    source_comparison_service.openai_enabled = False

    res = source_comparison_service._generate_deterministic_comparison(
        src_name="BBC",
        unique_summary="unique actors: Actor A",
        missing_summary="omitted targets: Target B",
        contradictions_summary="Contradicts Reuters on casualties.",
    )

    assert res.focus_area == "General coverage by BBC."
    assert res.unique_information == "unique actors: Actor A"
    assert res.missing_information == "omitted targets: Target B"
    assert res.contradictions == "Contradicts Reuters on casualties."


@pytest.mark.asyncio
@patch("app.services.ai_service.ai_service.summarize_story_from_kg")
@patch("app.services.ner_service_v2.ner_service_v2.extract_entities")
async def test_generate_story_content_redesigned_timeline(
    mock_extract_entities, mock_summarize_story, mock_db_session
):
    """Verify that generate_story_content builds a chronological timeline from events."""
    story_id = uuid.uuid4()
    story = Story(id=story_id)

    src_id = uuid.uuid4()
    src = Source(id=src_id, name="BBC")

    art1 = Article(id=uuid.uuid4(), source_id=src_id, title="Article 1")
    art2 = Article(id=uuid.uuid4(), source_id=src_id, title="Article 2")
    art1.source = src
    art2.source = src

    # Event 1: Later time
    evt1 = ArticleEvent(
        article_id=art1.id,
        event_type="DETENTION",
        event_type_canonical="DETENTION",
        actors=["Police"],
        targets=["Suspect"],
        location="Kyiv",
        event_time=datetime.datetime(2026, 6, 20, 15, 0, 0),  # Later
    )
    # Event 2: Earlier time
    evt2 = ArticleEvent(
        article_id=art2.id,
        event_type="ATTACK",
        event_type_canonical="ATTACK",
        actors=["Russia"],
        targets=["Kyiv"],
        location="Kyiv",
        event_time=datetime.datetime(2026, 6, 20, 10, 0, 0),  # Earlier
    )

    # Setup mocked DB session returns
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.scalar.return_value = None
        if "from sources" in stmt_str:
            res.scalar_one_or_none.return_value = src
        elif "from article_events" in stmt_str:
            res.scalars.return_value.all.return_value = [evt1, evt2]
        return res

    mock_db_session.execute.side_effect = mock_execute

    # Mock AI Synthesis returns
    from app.services.ai_service import StorySummaryResponse
    mock_summarize_story.return_value = StorySummaryResponse(
        headline="Headline",
        one_line_summary="One line",
        short_summary="Short summary",
        detailed_summary="Detailed summary",
        key_facts=["Fact 1"],
        category="world",
    )

    # Mock NER returns
    mock_extract_entities.return_value = []

    # Mock Contradiction & Source Comparison service calls to avoid hitting mock DB again
    with patch.object(contradiction_service, "detect_and_save_contradictions", AsyncMock(return_value=[])), \
         patch.object(source_comparison_service, "compare_sources_and_save", AsyncMock(return_value=([], []))), \
         patch.object(clustering_service, "_index_and_invalidate", AsyncMock()):

        await clustering_service.generate_story_content(story, [art1, art2], mock_db_session)

        # Verify added objects
        added_objects = [args[0] for args, _ in mock_db_session.add.call_args_list]

        # Filter out StoryTimelineEvents
        timeline_events = [obj for obj in added_objects if isinstance(obj, StoryTimelineEvent)]
        assert len(timeline_events) == 2

        # Verify chronological sorting (earlier event should be first)
        assert timeline_events[0].event_time == datetime.datetime(2026, 6, 20, 10, 0, 0)
        assert "Attack reported by BBC" in timeline_events[0].description
        assert "Actors: Russia" in timeline_events[0].description

        assert timeline_events[1].event_time == datetime.datetime(2026, 6, 20, 15, 0, 0)
        assert "Detention reported by BBC" in timeline_events[1].description
        assert "Actors: Police" in timeline_events[1].description


@pytest.mark.asyncio
async def test_source_comparison_single_source(mock_db_session):
    """Verify that source comparison returns empty list and deletes existing coverages/differences for single source story."""
    story_id = uuid.uuid4()
    src_id = uuid.uuid4()
    art = Article(id=uuid.uuid4(), title="Title", source_id=src_id)
    src = Source(id=src_id, name="BBC News", slug="bbc-news")

    mock_res = MagicMock()
    mock_res.all.return_value = [(art, src)]
    mock_db_session.execute.return_value = mock_res

    coverages, differences = await source_comparison_service.compare_sources_and_save(
        story_id, mock_db_session
    )

    assert coverages == []
    assert differences == []
    # Verify execute calls (delete coverages, delete differences, select articles)
    assert mock_db_session.execute.call_count >= 3
