"""Regression tests for the fail-open source comparison.

Production before this design (docs/Source_Comparison_Audit.md, 1,171 rows):
56-66% of "AI Comparative Analysis" columns were raw heuristic strings the
LLM never saw, 60% carried fabricated contradiction copies, 605 rows leaked
Python reprs, published_at was NULL on 93% of coverage rows and synthesis
wall-clock on the rest, and 49% of sampled rows listed the same fact as both
unique and missing.

Pinned here:
  1. an unreachable validator publishes nothing and leaves existing rows;
  2. raw heuristic strings can never reach the persisted columns;
  3. validated output is what gets stored, joined for the text columns;
  4. published_at is the source's article publish time;
  5. the cache key excludes the volatile story context.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.models import Article, ArticleEvent, Source
from app.services.source_comparison_service import (
    SourceComparisonResolution,
    SourceComparisonService,
)


class _RecordingSession:
    def __init__(self, entity_rows=None):
        self.statements = []
        self.added = []
        self._entity_rows = entity_rows or []

    async def execute(self, stmt):
        self.statements.append(stmt)

        class _Res:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

            def scalars(self):
                return self

        stmt_str = str(stmt).lower()
        if "article_entities" in stmt_str:
            return _Res(self._entity_rows)
        return _Res([])

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass

    def deletes(self):
        return [s for s in self.statements if s.__class__.__name__ == "Delete"]


def _story():
    """Two publishers whose actor lists are case variants plus real uniques."""
    src_a = Source(id=uuid.uuid4(), name="heraldscotland.com")
    src_b = Source(id=uuid.uuid4(), name="HuffPost")
    art_a = Article(
        id=uuid.uuid4(),
        source_id=src_a.id,
        title="A",
        published_at=datetime(2026, 8, 17, 9, 30),
    )
    art_b = Article(
        id=uuid.uuid4(),
        source_id=src_b.id,
        title="B",
        published_at=datetime(2026, 8, 17, 11, 0),
    )
    evt_a = ArticleEvent(
        article_id=art_a.id,
        actors=["Colombian government", "El Salvador"],
        targets=["civilian population"],
        location="western Colombia",
    )
    evt_b = ArticleEvent(
        article_id=art_b.id,
        actors=["Colombian Government", "Rescue Teams"],
        targets=["Civilians"],
        location="Colombia",
    )
    return [art_a, art_b], [evt_a, evt_b], [src_a, src_b], src_a, src_b


@pytest.mark.asyncio
async def test_unreachable_validator_publishes_nothing():
    """LLM down → no rows written, no rows deleted, empty return."""
    articles, events, sources, *_ = _story()
    service = SourceComparisonService()
    session = _RecordingSession()

    with patch.object(service, "_analyze_with_llm", AsyncMock(return_value=None)):
        cov, diff = await service.compare_sources_and_save(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            sources_list=sources,
            precomputed_contradictions=[],
        )

    assert (cov, diff) == ([], [])
    assert session.added == []
    assert session.deletes() == [], "existing rows must survive a validator outage"


@pytest.mark.asyncio
async def test_partial_validation_publishes_nothing():
    """One source validated, the other not → whole story is left alone."""
    articles, events, sources, *_ = _story()
    service = SourceComparisonService()
    session = _RecordingSession()

    answers = [
        SourceComparisonResolution(focus_area="Focus A."),
        None,
    ]

    with patch.object(service, "_analyze_with_llm", AsyncMock(side_effect=answers)):
        cov, diff = await service.compare_sources_and_save(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            sources_list=sources,
            precomputed_contradictions=[],
        )

    assert (cov, diff) == ([], [])
    assert session.added == []
    assert session.deletes() == []


@pytest.mark.asyncio
async def test_raw_heuristic_strings_never_reach_the_columns():
    """The persisted columns hold the validator's output, not the candidate
    summaries — the 'unique actors: …' / 'omitted actors: …' format must be
    impossible to publish."""
    articles, events, sources, src_a, _ = _story()
    service = SourceComparisonService()
    session = _RecordingSession()

    resolution = SourceComparisonResolution(
        focus_area="Focused on the aid response.",
        validated_unique_information=["Only this source names El Salvador as a donor."],
        validated_missing_information=[],
        validated_contradictions=[],
    )

    with patch.object(service, "_analyze_with_llm", AsyncMock(return_value=resolution)):
        cov, diff = await service.compare_sources_and_save(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            sources_list=sources,
            precomputed_contradictions=[],
        )

    assert len(diff) == 2
    for d in diff:
        for col in (d.unique_information, d.missing_information, d.contradictions):
            if col:
                assert not col.startswith(("unique ", "omitted ", "Mismatch on ")), (
                    f"raw heuristic string persisted: {col!r}"
                )
    a_diff = next(d for d in diff if d.source_id == src_a.id)
    assert a_diff.unique_information == "Only this source names El Salvador as a donor."
    assert a_diff.missing_information is None


@pytest.mark.asyncio
async def test_case_variants_are_not_offered_as_candidates():
    """'Colombian government' vs 'Colombian Government' must be filtered
    before the validator ever sees a candidate list."""
    articles, events, sources, *_ = _story()
    service = SourceComparisonService()
    session = _RecordingSession()
    seen: list[dict] = []

    async def capture(
        *, src_name, unique_summary, missing_summary, contradictions_summary, context
    ):
        seen.append({"src": src_name, "unique": unique_summary, "missing": missing_summary})
        return SourceComparisonResolution(focus_area="F.")

    with patch.object(service, "_analyze_with_llm", side_effect=capture):
        await service.compare_sources_and_save(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            sources_list=sources,
            precomputed_contradictions=[],
        )

    assert len(seen) == 2
    for call in seen:
        assert "Colombian" not in call["unique"], call
        assert "Colombian" not in call["missing"], call
    herald = next(c for c in seen if c["src"] == "heraldscotland.com")
    assert "El Salvador" in herald["unique"], "genuine uniques must survive filtering"


@pytest.mark.asyncio
async def test_published_at_is_the_articles_publish_time():
    """Not the synthesis wall clock (99% of dated production rows were >1h
    off) and not NULL (93% were)."""
    articles, events, sources, src_a, src_b = _story()
    service = SourceComparisonService()
    session = _RecordingSession()

    with patch.object(
        service,
        "_analyze_with_llm",
        AsyncMock(return_value=SourceComparisonResolution(focus_area="F.")),
    ):
        cov, _ = await service.compare_sources_and_save(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            sources_list=sources,
            precomputed_contradictions=[],
        )

    by_source = {c.source_id: c for c in cov}
    assert by_source[src_a.id].published_at == datetime(2026, 8, 17, 9, 30)
    assert by_source[src_b.id].published_at == datetime(2026, 8, 17, 11, 0)


@pytest.mark.asyncio
async def test_cache_key_excludes_story_context():
    """The key used to include context[:1000], which changed whenever any
    article joined the story — the cache never paid for itself."""
    service = SourceComparisonService()
    seen: list[tuple] = []

    async def run(context: str):
        with (
            patch("app.services.pipeline_cache.pipeline_cache") as cache,
            patch("app.ai.gateway.ai_gateway") as gateway,
        ):
            cache.get = AsyncMock(return_value=None)
            cache.set = AsyncMock()
            cache.composite_hash = lambda *parts: seen.append(parts) or "h"
            gateway.generate_stage = AsyncMock(side_effect=RuntimeError("down"))
            await service._analyze_with_llm(
                src_name="BBC",
                unique_summary="unique actors: X",
                missing_summary="",
                contradictions_summary="",
                context=context,
            )

    await run("three articles " + "x" * 500)
    await run("nine articles " + "y" * 900)

    assert len(seen) == 2
    assert seen[0] == seen[1], f"cache key varies with story context: {seen}"


@pytest.mark.asyncio
async def test_unreachable_gateway_returns_none_not_fallback():
    """_analyze_with_llm has no deterministic fallback left to reach."""
    service = SourceComparisonService()

    with (
        patch("app.services.pipeline_cache.pipeline_cache") as cache,
        patch("app.ai.gateway.ai_gateway") as gateway,
    ):
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.composite_hash = lambda *parts: "h"
        gateway.generate_stage = AsyncMock(side_effect=RuntimeError("429 RESOURCE_EXHAUSTED"))

        result = await service._analyze_with_llm(
            src_name="BBC",
            unique_summary="unique actors: X",
            missing_summary="",
            contradictions_summary="",
            context="ctx",
        )

    assert result is None


@pytest.mark.asyncio
async def test_payload_round_trip_preserves_published_at():
    """run_publisher_stage re-materializes coverage from the payload; the
    serialization in run_source_comparison_stage must carry published_at or
    the publisher rewrite nulls it (93% of production rows)."""
    import inspect

    from app.services import story_synthesis_service as sss

    src = inspect.getsource(sss)
    serialize_idx = src.find('"published_at": c.published_at.isoformat()')
    assert serialize_idx != -1, "coverage serialization must include published_at"
    rehydrate_idx = src.find('cov_entry.get("published_at")')
    assert rehydrate_idx != -1, "publisher-stage rehydration must read published_at"
