"""Contradiction Service — structured fact contradiction detection between news sources.

Uses a hybrid approach:
1. Local heuristics flag potential conflicts in actors, targets, locations, times, or numbers.
2. If potential conflicts are found, an LLM checks them in context to ensure high precision (gating false positives).
3. Verified contradictions are persisted to the database.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.models import Article, ArticleEvent, Source, StoryArticle, StoryContradiction
from app.schemas.synthesis_context import ArticleContext, EventContext

logger = logging.getLogger(__name__)


class ContradictionResolution(BaseModel):
    """Structured response from LLM validator."""

    is_contradiction: bool = Field(
        description="Whether the two reports represent a true contradiction (not just a subset or wording difference)"
    )
    description: str = Field(
        description="Clear, explainable description of the contradiction (e.g. 'Reuters reports 15 casualties, while BBC reports 50 casualties.')"
    )
    confidence: float = Field(
        description="0.0 to 1.0 confidence score of the contradiction assessment"
    )


class ContradictionService:
    """Detects and validates factual contradictions across articles in a story."""

    def __init__(self) -> None:
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=False,
    )
    async def _validate_with_llm(
        self,
        fact_type: str,
        val1: Any,
        val2: Any,
        source1_name: str,
        source2_name: str,
        context: str,
    ) -> ContradictionResolution:
        """Call Gemini/OpenAI to verify if a candidate mismatch is a true contradiction.

        Pipeline: cache check → Agno Agent → LLM Gateway fallback → heuristic fallback.
        """
        from app.ai.prompts.repository import prompt_repository
        from app.services.pipeline_cache import pipeline_cache

        # ── Cache check ───────────────────────────────────────────────────────
        prompt_tmpl = prompt_repository.get("contradiction_detection")
        prompt_version = prompt_tmpl.version
        model = prompt_repository.model_config("contradiction_detection").model

        content_hash = pipeline_cache.composite_hash(
            fact_type, str(val1), str(val2), context[:1000]
        )

        cached = await pipeline_cache.get(
            stage="contradiction_detection",
            model=model,
            prompt_version=prompt_version,
            content_hash=content_hash,
            temperature=0.1,
        )
        if cached is not None:
            try:
                return ContradictionResolution(**cached)
            except Exception as e:
                logger.warning("Failed to deserialize cached contradiction: %s", e)

        # ── Agno Agent (primary path) ─────────────────────────────────────────
        result: ContradictionResolution | None = None
        try:
            from app.agents.contradiction_agent import check_contradiction

            agent_res = await check_contradiction(
                fact_type=fact_type,
                val1=str(val1),
                val2=str(val2),
                source1_name=source1_name,
                source2_name=source2_name,
                context=context,
            )
            result = ContradictionResolution(
                is_contradiction=agent_res.contradiction,
                description=agent_res.explanation,
                confidence=agent_res.confidence,
            )
        except Exception as e:
            logger.warning("Agno Contradiction Agent failed: %s. Falling back.", e)

        # ── LLM Gateway fallback ──────────────────────────────────────────────
        if result is None:
            try:
                from app.ai.gateway import ai_gateway

                prompt_variables = {
                    "fact_type": fact_type,
                    "val1": val1,
                    "val2": val2,
                    "source1_name": source1_name,
                    "source2_name": source2_name,
                    "context": context[:3000],
                }

                response = await ai_gateway.generate_stage(
                    stage="contradiction_detection",
                    prompt_variables=prompt_variables,
                    schema=ContradictionResolution,
                )

                if response.parsed:
                    result = response.parsed
                else:
                    try:
                        import json

                        data = json.loads(response.content)
                        result = ContradictionResolution(**data)
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning("AI Gateway contradiction verification failed: %s", exc)

        # ── Heuristic fallback ────────────────────────────────────────────────
        if result is None:
            desc = f"Mismatch on {fact_type}: {source1_name} reports '{val1}', while {source2_name} reports '{val2}'."
            result = ContradictionResolution(
                is_contradiction=True,
                description=desc,
                confidence=0.70,
            )

        # ── Cache store ───────────────────────────────────────────────────────
        try:
            await pipeline_cache.set(
                stage="contradiction_detection",
                model=model,
                prompt_version=prompt_version,
                content_hash=content_hash,
                response_data=result.model_dump(mode="json"),
                temperature=0.1,
            )
        except Exception as e:
            logger.warning("Failed to cache contradiction result: %s", e)

        return result

    async def detect_and_save_contradictions(
        self,
        story_id: Any,
        session: AsyncSession,
        articles: list[ArticleContext] = None,
        article_events: list[EventContext] = None,
        article_source_map: dict[uuid.UUID, str] = None,
    ) -> list[StoryContradiction]:
        """Detect contradictions among the articles in a story and save them to the DB.

        First runs local heuristics, then validates with LLM.
        """
        # Fetch articles and their events if not provided
        rows: list[Any] = []
        if articles is None or article_events is None:
            stmt = (
                select(Article, ArticleEvent)
                .join(StoryArticle, StoryArticle.article_id == Article.id)
                .join(ArticleEvent, ArticleEvent.article_id == Article.id)
                .where(StoryArticle.story_id == story_id)
            )
            res = await session.execute(stmt)
            rows = list(res.all())

            # Build local source map since it wasn't provided
            local_source_map = {}
            for art, _ in rows:
                if art.id not in local_source_map:
                    if art.source:
                        local_source_map[art.id] = art.source.name
                    else:
                        local_source_map[art.id] = "Unknown Source"
        else:
            # Reconstruct rows mapping Article to its ArticleEvent(s)
            for art in articles:
                for evt in article_events:
                    if evt.article_id == art.id:
                        rows.append((art, evt))
            local_source_map = article_source_map or {}

        # Delete existing contradictions for this story to avoid duplication or stale data
        from sqlalchemy import delete

        await session.execute(
            delete(StoryContradiction).where(StoryContradiction.story_id == story_id)
        )

        # Check unique sources count to avoid contradiction checking on single-source stories
        unique_sources = {art.source_id for art, _ in rows if art.source_id}
        if len(unique_sources) < 2:
            if articles is None:
                await session.commit()
            else:
                await session.flush()
            return []

        # Build full text context for LLM disambiguation
        context_parts = []
        for art, evt in rows:
            src_name = local_source_map.get(art.id, "Unknown Source")
            context_parts.append(
                f"Source: {src_name}\nTitle: {art.title}\nContent: {art.description or ''}\n"
            )
        full_context = "\n".join(context_parts)

        # Candidate detection (pairwise comparison)
        candidates: list[dict[str, Any]] = []
        n_rows = len(rows)

        for i in range(n_rows):
            art1, evt1 = rows[i]
            src1_name = local_source_map.get(art1.id, "Unknown Source")
            src1_id = str(art1.source_id)

            for j in range(i + 1, n_rows):
                art2, evt2 = rows[j]
                src2_name = local_source_map.get(art2.id, "Unknown Source")
                src2_id = str(art2.source_id)

                if src1_id == src2_id:
                    continue  # Skip comparing same publisher

                # 1. Actors Conflict
                a1 = set(evt1.actors or [])
                a2 = set(evt2.actors or [])
                if a1 and a2 and a1.isdisjoint(a2):
                    candidates.append(
                        {
                            "fact_type": "actor",
                            "val1": sorted(list(a1)),
                            "val2": sorted(list(a2)),
                            "src1_name": src1_name,
                            "src2_name": src2_name,
                            "src1_id": src1_id,
                            "src2_id": src2_id,
                        }
                    )

                # 2. Targets Conflict
                t1 = set(evt1.targets or [])
                t2 = set(evt2.targets or [])
                if t1 and t2 and t1.isdisjoint(t2):
                    candidates.append(
                        {
                            "fact_type": "target",
                            "val1": sorted(list(t1)),
                            "val2": sorted(list(t2)),
                            "src1_name": src1_name,
                            "src2_name": src2_name,
                            "src1_id": src1_id,
                            "src2_id": src2_id,
                        }
                    )

                # 3. Location Conflict
                if evt1.location and evt2.location:
                    loc1 = evt1.location.strip().lower()
                    loc2 = evt2.location.strip().lower()
                    if loc1 != loc2 and loc1 not in loc2 and loc2 not in loc1:
                        candidates.append(
                            {
                                "fact_type": "location",
                                "val1": evt1.location,
                                "val2": evt2.location,
                                "src1_name": src1_name,
                                "src2_name": src2_name,
                                "src1_id": src1_id,
                                "src2_id": src2_id,
                            }
                        )

                # 4. Time Conflict
                if evt1.event_time and evt2.event_time:
                    diff_days = abs((evt1.event_time - evt2.event_time).days)
                    if diff_days > 1:
                        candidates.append(
                            {
                                "fact_type": "event_time",
                                "val1": evt1.event_time.isoformat(),
                                "val2": evt2.event_time.isoformat(),
                                "src1_name": src1_name,
                                "src2_name": src2_name,
                                "src1_id": src1_id,
                                "src2_id": src2_id,
                            }
                        )

                # 5. Numerical Conflict
                num1 = evt1.numbers or {}
                num2 = evt2.numbers or {}
                for key, val1 in num1.items():
                    if key in num2:
                        val2 = num2[key]
                        try:
                            v1 = float(val1)
                            v2 = float(val2)
                            # Flag if diff > 10% and absolute diff > 1
                            if abs(v1 - v2) > 1:
                                max_v = max(v1, v2)
                                pct_diff = abs(v1 - v2) / max_v if max_v else 0.0
                                if pct_diff > 0.10:
                                    candidates.append(
                                        {
                                            "fact_type": "number",
                                            "val1": f"{key}: {v1}",
                                            "val2": f"{key}: {v2}",
                                            "src1_name": src1_name,
                                            "src2_name": src2_name,
                                            "src1_id": src1_id,
                                            "src2_id": src2_id,
                                        }
                                    )
                        except (ValueError, TypeError):
                            pass

        # Validate candidates using hybrid validation pass (LLM)
        validated_contradictions: list[StoryContradiction] = []

        # Deduplicate candidates on fact_type + src1_id + src2_id to keep DB clean
        seen_pairs = set()

        for cand in candidates:
            pair_key = (cand["fact_type"], cand["src1_id"], cand["src2_id"])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Call LLM to confirm
            res_resolution = await self._validate_with_llm(
                fact_type=cand["fact_type"],
                val1=cand["val1"],
                val2=cand["val2"],
                source1_name=cand["src1_name"],
                source2_name=cand["src2_name"],
                context=full_context,
            )

            if res_resolution.is_contradiction:
                contradiction = StoryContradiction(
                    story_id=story_id,
                    fact_type=cand["fact_type"],
                    description=res_resolution.description,
                    confidence=res_resolution.confidence,
                    source_attribution={
                        cand["src1_id"]: str(cand["val1"]),
                        cand["src2_id"]: str(cand["val2"]),
                    },
                )
                session.add(contradiction)
                validated_contradictions.append(contradiction)

        if validated_contradictions:
            if articles is None:
                await session.commit()
            else:
                await session.flush()

        return validated_contradictions

    async def detect_and_save_contradictions_incremental(
        self,
        story_id: Any,
        new_article: Article,
        existing_articles: list[Article],
        session: AsyncSession,
    ) -> list[StoryContradiction]:
        """Detect contradictions introduced by a new article compared against existing ones in a story."""
        # Fetch events for the new article
        new_event_stmt = select(ArticleEvent).where(ArticleEvent.article_id == new_article.id)
        new_event_res = await session.execute(new_event_stmt)
        new_events = list(new_event_res.scalars().all())

        if not new_events:
            return []

        # Fetch events for existing articles
        existing_ids = [art.id for art in existing_articles]
        if not existing_ids:
            return []

        existing_event_stmt = (
            select(Article, ArticleEvent)
            .join(ArticleEvent, ArticleEvent.article_id == Article.id)
            .where(Article.id.in_(existing_ids))
        )
        existing_event_res = await session.execute(existing_event_stmt)
        existing_rows = list(existing_event_res.all())

        if not existing_rows:
            return []

        # Build source name lookup map explicitly to avoid lazy loading
        source_ids = list(
            {art.source_id for art in [new_article] + existing_articles if art.source_id}
        )
        source_name_by_id = {}
        if source_ids:
            src_res = await session.execute(
                select(Source.id, Source.name).where(Source.id.in_(source_ids))
            )
            source_name_by_id = {sid: name for sid, name in src_res.all()}

        # Build context
        context_parts = []
        for art in [new_article] + existing_articles:
            src_name = source_name_by_id.get(art.source_id, "Unknown Source")
            context_parts.append(
                f"Source: {src_name}\nTitle: {art.title}\nContent: {art.description or ''}\n"
            )
        full_context = "\n".join(context_parts)

        # Candidates (compare new events against existing ones)
        candidates = []
        new_src_name = source_name_by_id.get(new_article.source_id, "Unknown Source")
        new_src_id = str(new_article.source_id)

        for new_evt in new_events:
            for ext_art, ext_evt in existing_rows:
                ext_src_name = source_name_by_id.get(ext_art.source_id, "Unknown Source")
                ext_src_id = str(ext_art.source_id)

                if new_src_id == ext_src_id:
                    continue  # Skip comparing same publisher

                # 1. Actors Conflict
                a1 = set(new_evt.actors or [])
                a2 = set(ext_evt.actors or [])
                if a1 and a2 and a1.isdisjoint(a2):
                    candidates.append(
                        {
                            "fact_type": "actor",
                            "val1": sorted(list(a1)),
                            "val2": sorted(list(a2)),
                            "src1_name": new_src_name,
                            "src2_name": ext_src_name,
                            "src1_id": new_src_id,
                            "src2_id": ext_src_id,
                        }
                    )

                # 2. Targets Conflict
                t1 = set(new_evt.targets or [])
                t2 = set(ext_evt.targets or [])
                if t1 and t2 and t1.isdisjoint(t2):
                    candidates.append(
                        {
                            "fact_type": "target",
                            "val1": sorted(list(t1)),
                            "val2": sorted(list(t2)),
                            "src1_name": new_src_name,
                            "src2_name": ext_src_name,
                            "src1_id": new_src_id,
                            "src2_id": ext_src_id,
                        }
                    )

                # 3. Numbers Conflict
                num1 = new_evt.numbers or {}
                num2 = ext_evt.numbers or {}
                for k in num1.keys():
                    if k in num2 and num1[k] != num2[k]:
                        candidates.append(
                            {
                                "fact_type": k,
                                "val1": str(num1[k]),
                                "val2": str(num2[k]),
                                "src1_name": new_src_name,
                                "src2_name": ext_src_name,
                                "src1_id": new_src_id,
                                "src2_id": ext_src_id,
                            }
                        )

        validated_contradictions = []
        seen_pairs = set()

        for cand in candidates:
            pair_key = (cand["fact_type"], cand["src1_id"], cand["src2_id"])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Call LLM to confirm
            res_resolution = await self._validate_with_llm(
                fact_type=str(cand["fact_type"]),
                val1=cand["val1"],
                val2=cand["val2"],
                source1_name=str(cand["src1_name"]),
                source2_name=str(cand["src2_name"]),
                context=full_context,
            )

            if res_resolution.is_contradiction:
                contradiction = StoryContradiction(
                    story_id=story_id,
                    fact_type=str(cand["fact_type"]),
                    description=res_resolution.description,
                    confidence=res_resolution.confidence,
                    source_attribution={
                        cand["src1_id"]: str(cand["val1"]),
                        cand["src2_id"]: str(cand["val2"]),
                    },
                )
                session.add(contradiction)
                validated_contradictions.append(contradiction)

        if validated_contradictions:
            await session.commit()

        return validated_contradictions


contradiction_service = ContradictionService()
