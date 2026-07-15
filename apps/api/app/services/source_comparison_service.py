"""Source Comparison Service — compares source coverage of stories.

Analyzes the knowledge graph and article events to determine:
1. The primary focus of each publisher.
2. Unique details reported only by that publisher.
3. Key details omitted by that publisher but reported by others.
4. Factual contradictions involving that publisher.

Uses a hybrid approach: local heuristics calculate candidate differences,
and an LLM validates and generates readable summaries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.models import (
    Article,
    ArticleEvent,
    Source,
    StoryArticle,
    StoryContradiction,
    StoryDifference,
    StorySourceCoverage,
)

logger = logging.getLogger(__name__)


class SourceComparisonResolution(BaseModel):
    """Structured response from LLM validator."""

    focus_area: str = Field(
        description="A concise sentence (max 100 chars) summarizing this publisher's primary angle/focus on the event."
    )
    unique_information: str = Field(
        description="Details mentioned ONLY by this source, or empty string if none"
    )
    missing_information: str = Field(
        description="Key details omitted by this source that others covered, or empty string if none"
    )
    contradictions: str = Field(
        description="Factual contradictions or conflicting claims made by this source compared to others, or empty string if none"
    )


class SourceComparisonService:
    """Detects unique, missing, and contradictory facts per source in a story cluster."""

    def __init__(self) -> None:
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=False,
    )
    async def _analyze_with_llm(
        self,
        src_name: str,
        unique_summary: str,
        missing_summary: str,
        contradictions_summary: str,
        context: str,
    ) -> SourceComparisonResolution:
        """Call LLM to generate a clean, cohesive source comparison analysis.

        Pipeline: cache check → LLM call → cache store.
        """
        from app.ai.prompts.repository import prompt_repository
        from app.services.pipeline_cache import pipeline_cache

        # ── Cache check ───────────────────────────────────────────────────────
        prompt_tmpl = prompt_repository.get("source_comparison")
        prompt_version = prompt_tmpl.version
        model = prompt_repository.model_config("source_comparison").model

        content_hash = pipeline_cache.composite_hash(
            src_name,
            unique_summary or "",
            missing_summary or "",
            contradictions_summary or "",
            context[:1000],
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

        # ── LLM call (cache miss) ─────────────────────────────────────────────
        result: SourceComparisonResolution | None = None

        from app.ai.gateway import ai_gateway

        try:
            prompt_variables = {
                "src_name": src_name,
                "unique_summary": unique_summary or "None",
                "missing_summary": missing_summary or "None",
                "contradictions_summary": contradictions_summary or "None",
                "context": context[:3000],
            }

            response = await ai_gateway.generate_stage(
                stage="source_comparison",
                prompt_variables=prompt_variables,
                schema=SourceComparisonResolution,
            )

            if response.parsed:
                result = response.parsed
            else:
                try:
                    import json

                    data = json.loads(response.content)
                    result = SourceComparisonResolution(**data)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("AI Gateway source comparison failed for %s: %s", src_name, exc)

        # ── Deterministic fallback ───────────────────────────────────────────
        if result is None:
            result = self._generate_deterministic_comparison(
                src_name=src_name,
                unique_summary=unique_summary,
                missing_summary=missing_summary,
                contradictions_summary=contradictions_summary,
            )

        # ── Cache store ───────────────────────────────────────────────────────
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

    def _generate_deterministic_comparison(
        self,
        src_name: str,
        unique_summary: str,
        missing_summary: str,
        contradictions_summary: str,
    ) -> SourceComparisonResolution:
        """Helper to create a fallback resolution from heuristic strings."""
        focus_area = f"General coverage by {src_name}."
        return SourceComparisonResolution(
            focus_area=focus_area,
            unique_information=unique_summary,
            missing_information=missing_summary,
            contradictions=contradictions_summary,
        )

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
        """Compare sources in a story cluster, generate coverage/difference data, and save to DB."""
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
            # Build rows mapping Article to Source
            for art in articles:
                src = next((s for s in (sources_list or []) if s.id == art.source_id), None)
                if src:
                    rows.append((art, src))

        if not rows:
            from sqlalchemy import delete
            await session.execute(
                delete(StorySourceCoverage).where(StorySourceCoverage.story_id == story_id)
            )
            await session.execute(delete(StoryDifference).where(StoryDifference.story_id == story_id))
            if articles is None:
                await session.commit()
            else:
                await session.flush()
            return [], []

        unique_sources = {src.id for _, src in rows}
        if len(unique_sources) < 2:
            from sqlalchemy import delete
            await session.execute(
                delete(StorySourceCoverage).where(StorySourceCoverage.story_id == story_id)
            )
            await session.execute(delete(StoryDifference).where(StoryDifference.story_id == story_id))
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

        # 3. Group events by source ID
        events_by_source: dict[uuid.UUID, list[Any]] = {}
        source_by_id: dict[uuid.UUID, Source] = {}
        for art, src in rows:
            source_by_id[src.id] = src
            events_by_source[src.id] = []

        for evt in article_events:
            art_id = evt.article_id
            for art, src in rows:
                if art.id == art_id:
                    events_by_source[src.id].append(evt)
                    break

        # 4. Fetch contradictions for this story
        if precomputed_contradictions is not None:
            story_contradictions = precomputed_contradictions
        else:
            contra_stmt = select(StoryContradiction).where(StoryContradiction.story_id == story_id)
            contra_res = await session.execute(contra_stmt)
            story_contradictions = list(contra_res.scalars().all())

        # 5. Build context corpus for the LLM
        context_parts = []
        local_source_map = article_source_map or {}
        for art, src in rows:
            src_name = local_source_map.get(art.id, src.name)
            context_parts.append(
                f"Source: {src_name}\nTitle: {art.title}\nContent: {art.description or ''}\n"
            )
        full_context = "\n".join(context_parts)

        # 6. Compare each source
        saved_coverage: list[StorySourceCoverage] = []
        saved_differences: list[StoryDifference] = []

        for src_id, src_evts in events_by_source.items():
            source = source_by_id[src_id]
            src_name = source.name

            # Gather attributes for this source
            src_actors = set()
            src_targets = set()
            src_locations = set()
            src_numbers = set()
            src_event_types = set()

            for event in src_evts:
                if event.actors:
                    src_actors.update(event.actors)
                if event.targets:
                    src_targets.update(event.targets)
                if event.location:
                    src_locations.add(event.location)
                if event.numbers:
                    for k, v in event.numbers.items():
                        src_numbers.add(f"{k}: {v}")
                if event.event_type_canonical:
                    src_event_types.add(event.event_type_canonical)
                elif event.event_type:
                    src_event_types.add(event.event_type)

            # Gather attributes for other sources
            other_actors = set()
            other_targets = set()
            other_locations = set()
            other_numbers = set()

            for other_id, other_evts in events_by_source.items():
                if other_id == src_id:
                    continue
                for other_evt in other_evts:
                    if other_evt.actors:
                        other_actors.update(other_evt.actors)
                    if other_evt.targets:
                        other_targets.update(other_evt.targets)
                    if other_evt.location:
                        other_locations.add(other_evt.location)
                    if other_evt.numbers:
                        for k, v in other_evt.numbers.items():
                            other_numbers.add(f"{k}: {v}")

            # Compute set differences
            unique_actors = src_actors - other_actors
            unique_targets = src_targets - other_targets
            unique_locations = src_locations - other_locations
            unique_numbers = src_numbers - other_numbers

            missing_actors = other_actors - src_actors
            missing_targets = other_targets - src_targets
            missing_locations = other_locations - src_locations
            missing_numbers = other_numbers - src_numbers

            # Format heuristic summaries
            unique_parts = []
            if unique_actors:
                unique_parts.append(f"unique actors: {', '.join(sorted(list(unique_actors)))}")
            if unique_targets:
                unique_parts.append(f"unique targets: {', '.join(sorted(list(unique_targets)))}")
            if unique_locations:
                unique_parts.append(
                    f"unique locations: {', '.join(sorted(list(unique_locations)))}"
                )
            if unique_numbers:
                unique_parts.append(
                    f"unique numerical facts: {', '.join(sorted(list(unique_numbers)))}"
                )
            unique_summary = "; ".join(unique_parts)

            missing_parts = []
            if missing_actors:
                missing_parts.append(f"omitted actors: {', '.join(sorted(list(missing_actors)))}")
            if missing_targets:
                missing_parts.append(f"omitted targets: {', '.join(sorted(list(missing_targets)))}")
            if missing_locations:
                missing_parts.append(
                    f"omitted locations: {', '.join(sorted(list(missing_locations)))}"
                )
            if missing_numbers:
                missing_parts.append(
                    f"omitted numerical facts: {', '.join(sorted(list(missing_numbers)))}"
                )
            missing_summary = "; ".join(missing_parts)

            # Contradictions involving this source
            src_contras = []
            for c in story_contradictions:
                if str(src_id) in c.source_attribution:
                    src_contras.append(c.description)
            contradictions_summary = "; ".join(src_contras)

            # 7. Perform hybrid analysis/synthesis
            resolution = await self._analyze_with_llm(
                src_name=src_name,
                unique_summary=unique_summary,
                missing_summary=missing_summary,
                contradictions_summary=contradictions_summary,
                context=full_context,
            )

            # 8. Override focus_area if empty or default to event types if LLM fallback used
            focus_area = resolution.focus_area
            if not focus_area or focus_area == f"General coverage by {src_name}.":
                if src_event_types:
                    types_str = ", ".join(sorted(list(src_event_types))).replace("_", " ").lower()
                    focus_area = f"Focused on {types_str} details."
                else:
                    focus_area = "General coverage."

            # Max length constraint on focus_area
            focus_area = focus_area[:100]

            # Save StorySourceCoverage
            coverage = StorySourceCoverage(
                id=uuid.uuid4(),
                story_id=story_id,
                source_id=src_id,
                focus_area=focus_area,
                published_at=datetime.now(UTC).replace(tzinfo=None),
            )
            saved_coverage.append(coverage)

            # Save StoryDifference
            diff = StoryDifference(
                id=uuid.uuid4(),
                story_id=story_id,
                source_id=src_id,
                unique_information=resolution.unique_information or None,
                missing_information=resolution.missing_information or None,
                contradictions=resolution.contradictions or None,
            )
            saved_differences.append(diff)

        # Delete existing coverages and differences for this story to avoid duplication or stale data
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
