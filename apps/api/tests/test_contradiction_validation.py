"""Regression tests for the fail-open contradiction validator.

The candidate heuristics are deliberately loose — disjoint actor sets, any
location string that is not a substring of the other, a >10% numeric gap — and
the docstring is explicit that the LLM exists "to ensure high precision (gating
false positives)". That gate used to fail *open*: when no model could be
reached it returned is_contradiction=True with confidence 0.70 and the raw
candidate as its description.

Gemini's free tier was exhausted for most of the measurement window (29,524 of
30,170 calls returned RESOURCE_EXHAUSTED, and contradiction_detection alone was
26,152 of them), so the gate was almost never actually closed. Production held
3,988 contradictions, of which 3,748 (94%) carried exactly confidence 0.70 and
the boilerplate "Mismatch on {fact_type}: ..." description — never adjudicated
by any model. They render on the story page and are emitted as JSON-LD, so the
product was publishing machine-readable claims that two named publishers
contradicted each other on evidence no model had ever seen.

Pinned here:
  1. an unreachable validator yields no contradiction, ever;
  2. a partially-validated run does not rewrite the story's existing rows;
  3. one model chain per candidate, not two;
  4. the cache key does not carry the volatile story context.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.synthesis_context import ArticleContext, EventContext
from app.services.contradiction_service import ContradictionResolution, ContradictionService


def _article(source_id: uuid.UUID, title: str) -> ArticleContext:
    return ArticleContext(
        id=uuid.uuid4(),
        source_id=source_id,
        title=title,
        description="body",
        content=None,
        url=None,
        published_at=datetime.now(UTC),
    )


def _event(article_id: uuid.UUID, actors: list[str]) -> EventContext:
    return EventContext(
        id=uuid.uuid4(),
        article_id=article_id,
        event_type="incident",
        event_type_canonical="incident",
        location=None,
        event_time=None,
        event_time_raw=None,
        confidence=0.9,
        numbers=None,
        actors=actors,
        targets=None,
        event_fingerprint=None,
        created_at=datetime.now(UTC),
    )


class _RecordingSession:
    """Captures statements so a DELETE can be asserted absent."""

    def __init__(self) -> None:
        self.statements: list[object] = []
        self.added: list[object] = []
        self.flushed = False

    async def execute(self, stmt):  # noqa: ANN001 - test double
        self.statements.append(stmt)
        return None

    def add(self, obj) -> None:  # noqa: ANN001 - test double
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.flushed = True

    def deletes(self) -> list[object]:
        return [s for s in self.statements if s.__class__.__name__ == "Delete"]


@pytest.fixture
def two_source_story():
    """Two publishers with disjoint actor sets — one guaranteed candidate."""
    src_a, src_b = uuid.uuid4(), uuid.uuid4()
    art_a, art_b = _article(src_a, "A reports"), _article(src_b, "B reports")
    return (
        [art_a, art_b],
        [_event(art_a.id, ["Alice"]), _event(art_b.id, ["Bob"])],
        {art_a.id: "Source A", art_b.id: "Source B"},
    )


# ── 1. The gate must fail closed ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unreachable_validator_yields_no_contradiction():
    """A model that cannot be reached means "unknown", not "contradiction"."""
    service = ContradictionService()

    with (
        patch("app.services.pipeline_cache.pipeline_cache") as cache,
        patch("app.ai.gateway.ai_gateway") as gateway,
    ):
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.composite_hash = lambda *parts: "|".join(parts)
        gateway.generate_stage = AsyncMock(side_effect=RuntimeError("429 RESOURCE_EXHAUSTED"))

        result = await service._validate_with_llm(
            fact_type="actor",
            val1=["Alice"],
            val2=["Bob"],
            source1_name="Source A",
            source2_name="Source B",
            context="story context",
        )

    assert result is None, "an unreachable validator must not assert a contradiction"


@pytest.mark.asyncio
async def test_no_contradiction_persisted_when_validator_is_down(two_source_story):
    """End to end: quota exhaustion produces zero published contradictions."""
    articles, events, source_map = two_source_story
    service = ContradictionService()
    session = _RecordingSession()

    with (
        patch("app.services.pipeline_cache.pipeline_cache") as cache,
        patch("app.ai.gateway.ai_gateway") as gateway,
    ):
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.composite_hash = lambda *parts: "|".join(parts)
        gateway.generate_stage = AsyncMock(side_effect=RuntimeError("429 RESOURCE_EXHAUSTED"))

        saved = await service.detect_and_save_contradictions(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            article_source_map=source_map,
        )

    assert saved == []
    assert session.added == [], "nothing may be written when nothing was validated"


@pytest.mark.asyncio
async def test_the_0_70_heuristic_fallback_is_gone(two_source_story):
    """The exact signature of the 3,748 fabricated rows must be unreachable."""
    articles, events, source_map = two_source_story
    service = ContradictionService()
    session = _RecordingSession()

    with (
        patch("app.services.pipeline_cache.pipeline_cache") as cache,
        patch("app.ai.gateway.ai_gateway") as gateway,
    ):
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.composite_hash = lambda *parts: "|".join(parts)
        gateway.generate_stage = AsyncMock(side_effect=RuntimeError("down"))

        await service.detect_and_save_contradictions(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            article_source_map=source_map,
        )

    confidences = [getattr(c, "confidence", None) for c in session.added]
    descriptions = [getattr(c, "description", "") or "" for c in session.added]
    assert 0.70 not in confidences
    assert not any(d.startswith("Mismatch on ") for d in descriptions)


# ── 2. A partial run must not erase confirmed rows ───────────────────────────


@pytest.mark.asyncio
async def test_partial_validation_does_not_delete_existing_rows(two_source_story):
    """The wholesale rewrite is only safe when every candidate got an answer.

    Otherwise an outage deletes contradictions an earlier, healthy run
    confirmed and replaces them with a partial set.
    """
    articles, events, source_map = two_source_story
    service = ContradictionService()
    session = _RecordingSession()

    with (
        patch("app.services.pipeline_cache.pipeline_cache") as cache,
        patch("app.ai.gateway.ai_gateway") as gateway,
    ):
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.composite_hash = lambda *parts: "|".join(parts)
        gateway.generate_stage = AsyncMock(side_effect=RuntimeError("down"))

        await service.detect_and_save_contradictions(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            article_source_map=source_map,
        )

    assert session.deletes() == [], "an unvalidated run must leave stored rows alone"


@pytest.mark.asyncio
async def test_fully_validated_run_still_reconciles(two_source_story):
    """When every candidate is answered, the rewrite must still happen."""
    articles, events, source_map = two_source_story
    service = ContradictionService()
    session = _RecordingSession()

    with (
        patch("app.services.pipeline_cache.pipeline_cache") as cache,
        patch("app.ai.gateway.ai_gateway") as gateway,
    ):
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.composite_hash = lambda *parts: "|".join(parts)
        gateway.generate_stage = AsyncMock(
            return_value=type(
                "R",
                (),
                {
                    "parsed": ContradictionResolution(
                        is_contradiction=True,
                        description="A says Alice, B says Bob.",
                        confidence=0.93,
                    ),
                    "content": "",
                },
            )()
        )

        saved = await service.detect_and_save_contradictions(
            story_id=uuid.uuid4(),
            session=session,
            articles=articles,
            article_events=events,
            article_source_map=source_map,
        )

    assert len(saved) == 1
    assert saved[0].confidence == 0.93
    assert len(session.deletes()) == 1, "a complete run reconciles as before"


# ── 3. One model chain per candidate ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_failed_validation_does_not_run_a_second_chain():
    """Agent and gateway both resolved to stage=contradiction_detection.

    The "fallback" re-ran the same models with the same prompt, so it could
    only add a second failure — and it doubled the busiest stage in the
    pipeline: 26,152 of 30,170 LLM calls in a 15h window.
    """
    service = ContradictionService()

    with (
        patch("app.services.pipeline_cache.pipeline_cache") as cache,
        patch("app.ai.gateway.ai_gateway") as gateway,
        patch("app.agents.contradiction_agent.check_contradiction") as agent,
    ):
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.composite_hash = lambda *parts: "|".join(parts)
        gateway.generate_stage = AsyncMock(side_effect=RuntimeError("down"))
        agent.side_effect = AssertionError("the duplicate agent chain must not run")

        await service._validate_with_llm(
            fact_type="actor",
            val1=["Alice"],
            val2=["Bob"],
            source1_name="A",
            source2_name="B",
            context="ctx",
        )

    assert gateway.generate_stage.await_count == 1
    agent.assert_not_called()


# ── 4. The cache key must be stable across story growth ──────────────────────


@pytest.mark.asyncio
async def test_cache_key_excludes_story_context():
    """The key used to carry context[:1000].

    That changes whenever any article joins the story, so the same fact pair
    was re-validated from scratch on every synthesis run and the cache never
    paid for itself.
    """
    service = ContradictionService()
    seen: list[tuple] = []

    async def run(context: str) -> None:
        with (
            patch("app.services.pipeline_cache.pipeline_cache") as cache,
            patch("app.ai.gateway.ai_gateway") as gateway,
        ):
            cache.get = AsyncMock(return_value=None)
            cache.set = AsyncMock()
            cache.composite_hash = lambda *parts: seen.append(parts) or "h"
            gateway.generate_stage = AsyncMock(side_effect=RuntimeError("down"))
            await service._validate_with_llm(
                fact_type="number",
                val1="dead: 15.0",
                val2="dead: 50.0",
                source1_name="A",
                source2_name="B",
                context=context,
            )

    await run("story with three articles" + "x" * 500)
    await run("story with nine articles" + "y" * 900)

    assert len(seen) == 2
    assert seen[0] == seen[1], f"cache key varies with story context: {seen}"
    assert all("x" * 20 not in part and "y" * 20 not in part for part in seen[0])
