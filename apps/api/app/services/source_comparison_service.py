"""Source Comparison Service — validated cross-source coverage differences.

Heuristics generate candidates; a validator LLM confirms them; only confirmed
facts reach the user. Measured before this design (2026-08-18, 1,171 rows):
56-66% of published "differences" were raw heuristic strings the LLM never
saw, 60% carried fabricated contradiction text, and 49% of sampled rows listed
a fact as unique to a source that also appeared in the same row's "missing"
list once lowercased. docs/Source_Comparison_Audit.md holds the full audit.

The three layers, in order:

1. Candidates come from set differences over *normalized* facts
   (fact_normalization.py), resolved through the canonical-entity layer where
   entity linking has done its work — so case variants, aliases and
   containment duplicates never become candidates at all.
2. The LLM is a validator, not a formatter: it rejects paraphrases and
   subsets against the article context, and its rejections are recorded.
3. No validator, no analysis: when the LLM is unreachable the story's
   existing comparison rows are left untouched and nothing new is published.
   The UI hides the section when no rows exist — an absent comparison is
   honest, fallback prose is not.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import (
    newsiq_comparison_candidates_total,
    newsiq_comparison_unavailable_total,
)
from app.models.models import (
    Article,
    ArticleEntity,
    ArticleEvent,
    CanonicalEntity,
    Source,
    StoryArticle,
    StoryContradiction,
    StoryDifference,
    StorySourceCoverage,
)
from app.services.fact_normalization import (
    CanonicalResolver,
    normalize_fact,
    numbers_conflict,
    partition_unique,
)

logger = logging.getLogger(__name__)


class RejectedCandidate(BaseModel):
    """A heuristic candidate the validator refused, kept for audit."""

    candidate: str = Field(description="The candidate difference, verbatim")
    reason: str = Field(description="Why it is not a genuine difference (e.g. 'case-only variant')")


class SourceComparisonResolution(BaseModel):
    """Structured response from the validator LLM."""

    focus_area: str = Field(
        description="One sentence (max 100 chars) on this publisher's angle, grounded in the articles"
    )
    validated_unique_information: list[str] = Field(
        default_factory=list,
        description="Facts genuinely reported only by this source; empty when none survive",
    )
    validated_missing_information: list[str] = Field(
        default_factory=list,
        description="Facts genuinely omitted by this source that others report; empty when none survive",
    )
    validated_contradictions: list[str] = Field(
        default_factory=list,
        description="Genuine factual conflicts involving this source; empty when none survive",
    )
    rejected_candidates: list[RejectedCandidate] = Field(
        default_factory=list,
        description="Candidates rejected as variants/aliases/paraphrases/subsets, with reasons",
    )


def _join(items: list[str]) -> str | None:
    cleaned = [i.strip() for i in items if i and i.strip()]
    return "; ".join(cleaned) if cleaned else None


class SourceComparisonService:
    """Detects and validates unique, missing, and contradictory facts per source."""

    async def _build_resolver(
        self, session: AsyncSession, article_ids: list[uuid.UUID]
    ) -> CanonicalResolver:
        """Canonical-entity lookup for this story's articles.

        Surface forms come from article_entities; canonical names and aliases
        from canonical_entities — so "US", "United States" and "U.S." compare
        equal wherever entity linking has resolved them.
        """
        resolver = CanonicalResolver()
        if not article_ids:
            return resolver

        rows = (
            await session.execute(
                select(
                    ArticleEntity.entity_value,
                    ArticleEntity.canonical_entity_id,
                    CanonicalEntity.canonical_name,
                    CanonicalEntity.aliases,
                )
                .join(CanonicalEntity, CanonicalEntity.id == ArticleEntity.canonical_entity_id)
                .where(ArticleEntity.article_id.in_(article_ids))
                .where(ArticleEntity.canonical_entity_id.is_not(None))
            )
        ).all()

        for surface, canonical_id, canonical_name, aliases in rows:
            resolver.add(surface, canonical_id)
            resolver.add(canonical_name, canonical_id)
            for alias in aliases or []:
                if isinstance(alias, str):
                    resolver.add(alias, canonical_id)
        return resolver

    async def _analyze_with_llm(
        self,
        src_name: str,
        unique_summary: str,
        missing_summary: str,
        contradictions_summary: str,
        context: str,
    ) -> SourceComparisonResolution | None:
        """Validate this source's candidates. Returns None when no model answers.

        There is no deterministic fallback. The previous one published the raw
        heuristic strings verbatim under an "AI Comparative Analysis" banner —
        56-66% of all production rows — and an unreachable validator must mean
        "no analysis", never "unvalidated analysis".
        """
        from app.ai.prompts.repository import prompt_repository
        from app.services.pipeline_cache import pipeline_cache

        prompt_tmpl = prompt_repository.get("source_comparison")
        prompt_version = prompt_tmpl.version
        model = prompt_repository.model_config("source_comparison").model

        # Keyed on the candidates alone. The key used to include
        # context[:1000], which changed whenever any article joined the story,
        # so the cache effectively never hit.
        content_hash = pipeline_cache.composite_hash(
            src_name,
            unique_summary or "",
            missing_summary or "",
            contradictions_summary or "",
        )

        cached = await pipeline_cache.get(
            stage="source_comparison",
            model=model,
            prompt_version=prompt_version,
            content_hash=content_hash,
            temperature=0.1,
        )
        if cached is not None:
            try:
                return SourceComparisonResolution(**cached)
            except Exception as e:
                logger.warning("Failed to deserialize cached source comparison: %s", e)

        result: SourceComparisonResolution | None = None

        from app.ai.gateway import ai_gateway

        try:
            response = await ai_gateway.generate_stage(
                stage="source_comparison",
                prompt_variables={
                    "src_name": src_name,
                    "unique_summary": unique_summary or "None",
                    "missing_summary": missing_summary or "None",
                    "contradictions_summary": contradictions_summary or "None",
                    "context": context[:3000],
                },
                schema=SourceComparisonResolution,
            )

            if response.parsed:
                result = response.parsed
            else:
                try:
                    import json

                    result = SourceComparisonResolution(**json.loads(response.content))
                except Exception:
                    logger.warning(
                        "Source comparison validator returned unparseable content for %s; "
                        "treating as unavailable.",
                        src_name,
                    )
        except Exception as exc:
            logger.warning("AI Gateway source comparison failed for %s: %s", src_name, exc)

        if result is None:
            return None

        for rejected in result.rejected_candidates:
            logger.info(
                "source_comparison rejected candidate for %s: %r (%s)",
                src_name,
                rejected.candidate,
                rejected.reason,
            )
        kept = (
            len(result.validated_unique_information)
            + len(result.validated_missing_information)
            + len(result.validated_contradictions)
        )
        newsiq_comparison_candidates_total.labels(disposition="validated").inc(kept)
        newsiq_comparison_candidates_total.labels(disposition="rejected").inc(
            len(result.rejected_candidates)
        )

        try:
            await pipeline_cache.set(
                stage="source_comparison",
                model=model,
                prompt_version=prompt_version,
                content_hash=content_hash,
                response_data=result.model_dump(mode="json"),
                temperature=0.1,
            )
        except Exception as e:
            logger.warning("Failed to cache source comparison result: %s", e)

        return result

    async def compare_sources_and_save(
        self,
        story_id: Any,
        session: AsyncSession,
        articles: list[Any] = None,
        article_events: list[Any] = None,
        article_source_map: dict[uuid.UUID, str] = None,
        sources_list: list[Any] = None,
        precomputed_contradictions: list[StoryContradiction] = None,
    ) -> tuple[list[StorySourceCoverage], list[StoryDifference]]:
        """Compare sources in a story cluster and persist validated results.

        Fails closed: if any source's candidates cannot be validated, the
        story's existing rows are left untouched and nothing is returned.
        """
        # 1. Fetch articles and sources in story if not provided
        rows: list[Any] = []
        if articles is None:
            stmt = (
                select(Article, Source)
                .join(StoryArticle, StoryArticle.article_id == Article.id)
                .join(Source, Source.id == Article.source_id)
                .where(StoryArticle.story_id == story_id)
            )
            res = await session.execute(stmt)
            rows = list(res.all())
        else:
            for art in articles:
                src = next((s for s in (sources_list or []) if s.id == art.source_id), None)
                if src:
                    rows.append((art, src))

        unique_sources = {src.id for _, src in rows}
        if len(unique_sources) < 2:
            # A one-source story has no cross-source comparison; stale rows
            # from when it had more sources would be wrong to keep.
            from sqlalchemy import delete

            await session.execute(
                delete(StorySourceCoverage).where(StorySourceCoverage.story_id == story_id)
            )
            await session.execute(
                delete(StoryDifference).where(StoryDifference.story_id == story_id)
            )
            if articles is None:
                await session.commit()
            else:
                await session.flush()
            return [], []

        # 2. Fetch article events
        if article_events is None:
            article_ids = [art.id for art, _ in rows]
            evt_stmt = select(ArticleEvent).where(ArticleEvent.article_id.in_(article_ids))
            evt_res = await session.execute(evt_stmt)
            article_events = list(evt_res.scalars().all())

        # 3. Group events and articles by source
        events_by_source: dict[uuid.UUID, list[Any]] = {}
        articles_by_source: dict[uuid.UUID, list[Any]] = {}
        source_by_id: dict[uuid.UUID, Source] = {}
        for art, src in rows:
            source_by_id[src.id] = src
            events_by_source.setdefault(src.id, [])
            articles_by_source.setdefault(src.id, []).append(art)

        article_to_source = {art.id: src.id for art, src in rows}
        for evt in article_events:
            src_id = article_to_source.get(evt.article_id)
            if src_id is not None:
                events_by_source[src_id].append(evt)

        # 4. Contradictions for this story
        if precomputed_contradictions is not None:
            story_contradictions = precomputed_contradictions
        else:
            contra_res = await session.execute(
                select(StoryContradiction).where(StoryContradiction.story_id == story_id)
            )
            story_contradictions = list(contra_res.scalars().all())

        # 5. Canonical-entity resolver + LLM context corpus
        resolver = await self._build_resolver(session, [art.id for art, _ in rows])

        local_source_map = article_source_map or {}
        context_parts = []
        for art, src in rows:
            src_name = local_source_map.get(art.id, src.name)
            context_parts.append(
                f"Source: {src_name}\nTitle: {art.title}\nContent: {art.description or ''}\n"
            )
        full_context = "\n".join(context_parts)

        # 6. Per-source candidate generation and validation
        saved_coverage: list[StorySourceCoverage] = []
        saved_differences: list[StoryDifference] = []

        for src_id, src_evts in events_by_source.items():
            source = source_by_id[src_id]
            src_name = source.name

            src_actors: set[str] = set()
            src_targets: set[str] = set()
            src_locations: set[str] = set()
            src_numbers: dict[str, Any] = {}

            for event in src_evts:
                src_actors.update(event.actors or [])
                src_targets.update(event.targets or [])
                if event.location:
                    src_locations.add(event.location)
                for k, v in (event.numbers or {}).items():
                    src_numbers.setdefault(normalize_fact(k), v)

            other_actors: set[str] = set()
            other_targets: set[str] = set()
            other_locations: set[str] = set()
            other_numbers: dict[str, Any] = {}

            for other_id, other_evts in events_by_source.items():
                if other_id == src_id:
                    continue
                for other_evt in other_evts:
                    other_actors.update(other_evt.actors or [])
                    other_targets.update(other_evt.targets or [])
                    if other_evt.location:
                        other_locations.add(other_evt.location)
                    for k, v in (other_evt.numbers or {}).items():
                        other_numbers.setdefault(normalize_fact(k), v)

            # Normalized, canonically-resolved set differences. Case variants,
            # aliases and containment duplicates never become candidates.
            unique_actors = partition_unique(src_actors, other_actors, resolver)
            unique_targets = partition_unique(src_targets, other_targets, resolver)
            unique_locations = partition_unique(src_locations, other_locations, resolver)
            missing_actors = partition_unique(other_actors, src_actors, resolver)
            missing_targets = partition_unique(other_targets, src_targets, resolver)
            missing_locations = partition_unique(other_locations, src_locations, resolver)

            unique_numbers: set[str] = set()
            missing_numbers: set[str] = set()
            conflicting_numbers: set[str] = set()
            for key, val in src_numbers.items():
                if key not in other_numbers:
                    unique_numbers.add(f"{key}: {val}")
                elif numbers_conflict(val, other_numbers[key]):
                    conflicting_numbers.add(f"{key}: {val} vs {other_numbers[key]}")
            for key, val in other_numbers.items():
                if key not in src_numbers:
                    missing_numbers.add(f"{key}: {val}")

            unique_parts = []
            if unique_actors:
                unique_parts.append(f"unique actors: {', '.join(sorted(unique_actors))}")
            if unique_targets:
                unique_parts.append(f"unique targets: {', '.join(sorted(unique_targets))}")
            if unique_locations:
                unique_parts.append(f"unique locations: {', '.join(sorted(unique_locations))}")
            if unique_numbers:
                unique_parts.append(f"unique numerical facts: {', '.join(sorted(unique_numbers))}")
            unique_summary = "; ".join(unique_parts)

            missing_parts = []
            if missing_actors:
                missing_parts.append(f"omitted actors: {', '.join(sorted(missing_actors))}")
            if missing_targets:
                missing_parts.append(f"omitted targets: {', '.join(sorted(missing_targets))}")
            if missing_locations:
                missing_parts.append(f"omitted locations: {', '.join(sorted(missing_locations))}")
            if missing_numbers:
                missing_parts.append(
                    f"omitted numerical facts: {', '.join(sorted(missing_numbers))}"
                )
            missing_summary = "; ".join(missing_parts)

            src_contras = [
                c.description
                for c in story_contradictions
                if str(src_id) in (c.source_attribution or {})
            ]
            src_contras.extend(sorted(conflicting_numbers))
            contradictions_summary = "; ".join(src_contras)

            resolution = await self._analyze_with_llm(
                src_name=src_name,
                unique_summary=unique_summary,
                missing_summary=missing_summary,
                contradictions_summary=contradictions_summary,
                context=full_context,
            )

            if resolution is None:
                # Fail closed for the whole story: partial rewrites would
                # replace rows a healthy run validated with an incomplete set.
                newsiq_comparison_unavailable_total.inc()
                logger.warning(
                    "Story %s: source comparison validator unavailable for %s; "
                    "leaving existing comparison rows untouched.",
                    story_id,
                    src_name,
                )
                return [], []

            focus_area = (resolution.focus_area or "").strip()[:100] or "General coverage."

            # published_at is this source's article publish time — previously
            # it was stamped with the synthesis wall clock, which is why 99%
            # of dated rows disagreed with their article by over an hour.
            published_times = [
                art.published_at
                for art in articles_by_source.get(src_id, [])
                if getattr(art, "published_at", None)
            ]
            published_at = min(published_times) if published_times else None
            if published_at is not None and published_at.tzinfo is not None:
                published_at = published_at.replace(tzinfo=None)

            saved_coverage.append(
                StorySourceCoverage(
                    id=uuid.uuid4(),
                    story_id=story_id,
                    source_id=src_id,
                    focus_area=focus_area,
                    published_at=published_at,
                )
            )
            saved_differences.append(
                StoryDifference(
                    id=uuid.uuid4(),
                    story_id=story_id,
                    source_id=src_id,
                    unique_information=_join(resolution.validated_unique_information),
                    missing_information=_join(resolution.validated_missing_information),
                    contradictions=_join(resolution.validated_contradictions),
                )
            )

        # 7. Every source validated — reconcile
        from sqlalchemy import delete

        await session.execute(
            delete(StorySourceCoverage).where(StorySourceCoverage.story_id == story_id)
        )
        await session.execute(delete(StoryDifference).where(StoryDifference.story_id == story_id))

        for cov in saved_coverage:
            session.add(cov)
        for diff in saved_differences:
            session.add(diff)

        if articles is None:
            await session.commit()
        else:
            await session.flush()

        return saved_coverage, saved_differences


source_comparison_service = SourceComparisonService()
