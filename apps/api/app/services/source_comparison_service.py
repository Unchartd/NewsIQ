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

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.models import (
    Article,
    ArticleEvent,
    Story,
    Source,
    StorySourceCoverage,
    StoryDifference,
    StoryContradiction,
    StoryArticle,
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
        """Call LLM to generate a clean, cohesive source comparison analysis."""
        prompt = (
            f"You are a professional news intelligence analyst.\n"
            f"Analyze the coverage of the publisher '{src_name}' for a story.\n\n"
            f"Here are the differences and coverages detected by our heuristic engines:\n"
            f"1. Unique facts reported only by {src_name}: {unique_summary or 'None'}\n"
            f"2. Facts reported by others but omitted by {src_name}: {missing_summary or 'None'}\n"
            f"3. Factual contradictions involving {src_name}: {contradictions_summary or 'None'}\n\n"
            f"Context from the story's articles:\n{context[:3000]}\n\n"
            f"Based on the heuristics and the articles' context, synthesize a clean analysis.\n"
            f"For 'focus_area', write a concise, professional sentence (max 100 chars, e.g. 'Detailed legal proceedings and arrest details.') summarizing their coverage angle.\n"
            f"For 'unique_information', 'missing_information', and 'contradictions', provide a concise, readable description. If none, return empty string.\n\n"
            f"Respond in JSON matching this schema:\n"
            f'{{"focus_area": "...", "unique_information": "...", "missing_information": "...", "contradictions": "..."}}'
        )

        model = settings.SUMMARIZATION_MODEL or "gemini-2.5-flash-lite"
        
        from app.llm_gateway.request_manager import llm_gateway

        try:
            response = await llm_gateway.execute_request(
                model=model,
                stage="source_comparison",
                messages=[{"role": "user", "content": prompt}],
                response_format=SourceComparisonResolution,
                temperature=0.1,
            )

            if response.parsed:
                return response.parsed
            
            try:
                import json
                data = json.loads(response.content)
                return SourceComparisonResolution(**data)
            except Exception:
                pass
        except Exception as exc:
            logger.warning("LLM Gateway source comparison failed for %s: %s", src_name, exc)

        # Fallback to deterministic representation
        return self._generate_deterministic_comparison(
            src_name=src_name,
            unique_summary=unique_summary,
            missing_summary=missing_summary,
            contradictions_summary=contradictions_summary,
        )

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
        self, story_id: Any, session: AsyncSession
    ) -> tuple[list[StorySourceCoverage], list[StoryDifference]]:
        """Compare sources in a story cluster, generate coverage/difference data, and save to DB."""
        # 1. Fetch articles and sources in story
        stmt = (
            select(Article, Source)
            .join(StoryArticle, StoryArticle.article_id == Article.id)
            .join(Source, Source.id == Article.source_id)
            .where(StoryArticle.story_id == story_id)
        )
        res = await session.execute(stmt)
        rows = list(res.all())

        # Delete existing coverages and differences for this story to avoid duplication or stale data
        from sqlalchemy import delete
        await session.execute(delete(StorySourceCoverage).where(StorySourceCoverage.story_id == story_id))
        await session.execute(delete(StoryDifference).where(StoryDifference.story_id == story_id))

        if not rows:
            await session.commit()
            return [], []

        unique_sources = {src.id for _, src in rows}
        if len(unique_sources) < 2:
            await session.commit()
            return [], []

        # 2. Fetch article events
        article_ids = [art.id for art, _ in rows]
        evt_stmt = select(ArticleEvent).where(ArticleEvent.article_id.in_(article_ids))
        evt_res = await session.execute(evt_stmt)
        article_events = list(evt_res.scalars().all())

        # 3. Group events by source ID
        events_by_source: dict[uuid.UUID, list[ArticleEvent]] = {}
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
        contra_stmt = select(StoryContradiction).where(StoryContradiction.story_id == story_id)
        contra_res = await session.execute(contra_stmt)
        story_contradictions = list(contra_res.scalars().all())

        # 5. Build context corpus for the LLM
        context_parts = []
        for art, src in rows:
            context_parts.append(
                f"Source: {src.name}\nTitle: {art.title}\nContent: {art.description or ''}\n"
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

            for evt in src_evts:
                if evt.actors:
                    src_actors.update(evt.actors)
                if evt.targets:
                    src_targets.update(evt.targets)
                if evt.location:
                    src_locations.add(evt.location)
                if evt.numbers:
                    for k, v in evt.numbers.items():
                        src_numbers.add(f"{k}: {v}")
                if evt.event_type_canonical:
                    src_event_types.add(evt.event_type_canonical)
                elif evt.event_type:
                    src_event_types.add(evt.event_type)

            # Gather attributes for other sources
            other_actors = set()
            other_targets = set()
            other_locations = set()
            other_numbers = set()

            for other_id, other_evts in events_by_source.items():
                if other_id == src_id:
                    continue
                for evt in other_evts:
                    if evt.actors:
                        other_actors.update(evt.actors)
                    if evt.targets:
                        other_targets.update(evt.targets)
                    if evt.location:
                        other_locations.add(evt.location)
                    if evt.numbers:
                        for k, v in evt.numbers.items():
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
                unique_parts.append(f"unique locations: {', '.join(sorted(list(unique_locations)))}")
            if unique_numbers:
                unique_parts.append(f"unique numerical facts: {', '.join(sorted(list(unique_numbers)))}")
            unique_summary = "; ".join(unique_parts)

            missing_parts = []
            if missing_actors:
                missing_parts.append(f"omitted actors: {', '.join(sorted(list(missing_actors)))}")
            if missing_targets:
                missing_parts.append(f"omitted targets: {', '.join(sorted(list(missing_targets)))}")
            if missing_locations:
                missing_parts.append(f"omitted locations: {', '.join(sorted(list(missing_locations)))}")
            if missing_numbers:
                missing_parts.append(f"omitted numerical facts: {', '.join(sorted(list(missing_numbers)))}")
            missing_summary = "; ".join(missing_parts)

            # Contradictions involving this source
            src_contras = []
            for c in story_contradictions:
                if str(src_id) in c.source_attribution:
                    src_contras.append(c.description)
            contradictions_summary = "; ".join(src_contras)

            # 7. Perform hybrid analysis/synthesis
            res = await self._analyze_with_llm(
                src_name=src_name,
                unique_summary=unique_summary,
                missing_summary=missing_summary,
                contradictions_summary=contradictions_summary,
                context=full_context,
            )

            # 8. Override focus_area if empty or default to event types if LLM fallback used
            focus_area = res.focus_area
            if not focus_area or focus_area == f"General coverage by {src_name}.":
                if src_event_types:
                    types_str = ", ".join(sorted(list(src_event_types))).replace("_", " ").lower()
                    focus_area = f"Focused on {types_str} details."
                else:
                    focus_area = f"General coverage."

            # Max length constraint on focus_area
            focus_area = focus_area[:100]

            # Save StorySourceCoverage
            coverage = StorySourceCoverage(
                id=uuid.uuid4(),
                story_id=story_id,
                source_id=src_id,
                focus_area=focus_area,
                published_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(coverage)
            saved_coverage.append(coverage)

            # Save StoryDifference
            diff = StoryDifference(
                id=uuid.uuid4(),
                story_id=story_id,
                source_id=src_id,
                unique_information=res.unique_information or None,
                missing_information=res.missing_information or None,
                contradictions=res.contradictions or None,
            )
            session.add(diff)
            saved_differences.append(diff)

        if saved_coverage or saved_differences:
            await session.commit()

        return saved_coverage, saved_differences


source_comparison_service = SourceComparisonService()
