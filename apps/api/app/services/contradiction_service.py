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

from app.core.metrics import newsiq_contradiction_unvalidated_total
from app.models.models import Article, ArticleEvent, Source, StoryArticle, StoryContradiction
from app.schemas.synthesis_context import ArticleContext, EventContext
from app.services.fact_normalization import (
    facts_equivalent,
    numbers_conflict,
    sets_share_a_fact,
)

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

    async def _validate_with_llm(
        self,
        fact_type: str,
        val1: Any,
        val2: Any,
        source1_name: str,
        source2_name: str,
        context: str,
    ) -> ContradictionResolution | None:
        """Verify that a candidate mismatch is a true contradiction.

        Pipeline: cache check → LLM Gateway → give up.

        Returns None when the model could not be reached. The heuristics that
        produce candidates are deliberately loose — disjoint actor sets, any
        location string mismatch, a >10% numeric gap — and the LLM is the only
        thing standing between a candidate and a published claim that two named
        publishers contradict each other. There is no honest way to make that
        judgement without it, so an unreachable model means "unknown", never
        "contradiction".
        """
        from app.ai.prompts.repository import prompt_repository
        from app.services.pipeline_cache import pipeline_cache

        # ── Cache check ───────────────────────────────────────────────────────
        prompt_tmpl = prompt_repository.get("contradiction_detection")
        prompt_version = prompt_tmpl.version
        model = prompt_repository.model_config("contradiction_detection").model

        # Keyed on the fact pair alone. The story context used to be part of
        # this hash, which meant the key changed every time any article joined
        # the story and the cache never hit — the same "15 dead vs 50 dead"
        # pair was re-validated from scratch on every synthesis run.
        content_hash = pipeline_cache.composite_hash(fact_type, str(val1), str(val2))

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

        # ── LLM Gateway ───────────────────────────────────────────────────────
        # This used to try the Agno contradiction agent first and fall through
        # to the gateway. Both resolve to GatewayModel(stage=
        # "contradiction_detection"), so the "fallback" re-ran the same model
        # chain with the same prompt — it could only ever add a second failure,
        # and it doubled the call volume on the busiest stage in the pipeline.
        result: ContradictionResolution | None = None
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
                    logger.warning(
                        "Contradiction validator returned unparseable content for "
                        "fact_type=%s; treating as unvalidated.",
                        fact_type,
                    )
        except Exception as exc:
            logger.warning("AI Gateway contradiction verification failed: %s", exc)

        if result is None:
            newsiq_contradiction_unvalidated_total.labels(fact_type=fact_type).inc()
            return None

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

        # Check unique sources count to avoid contradiction checking on single-source stories
        unique_sources = {art.source_id for art, _ in rows if art.source_id}
        if len(unique_sources) < 2:
            from sqlalchemy import delete

            await session.execute(
                delete(StoryContradiction).where(StoryContradiction.story_id == story_id)
            )
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

                # 1. Actors Conflict — "disjoint" must mean no equivalent
                # facts, not no byte-identical strings. The verbatim test
                # fired on pure case variants ("Colombian government" vs
                # "Colombian Government").
                a1 = set(evt1.actors or [])
                a2 = set(evt2.actors or [])
                if a1 and a2 and not sets_share_a_fact(a1, a2):
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
                if t1 and t2 and not sets_share_a_fact(t1, t2):
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

                # 3. Location Conflict — equivalence includes punctuation
                # and article stripping, not just lowercase containment.
                if evt1.location and evt2.location:
                    if not facts_equivalent(evt1.location, evt2.location):
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

                # 5. Numerical Conflict (>10% relative AND >1 absolute)
                num1 = evt1.numbers or {}
                num2 = evt2.numbers or {}
                for key, val1 in num1.items():
                    if key in num2 and numbers_conflict(val1, num2[key]):
                        candidates.append(
                            {
                                "fact_type": "number",
                                "val1": f"{key}: {val1}",
                                "val2": f"{key}: {num2[key]}",
                                "src1_name": src1_name,
                                "src2_name": src2_name,
                                "src1_id": src1_id,
                                "src2_id": src2_id,
                            }
                        )

        # Validate candidates using hybrid validation pass (LLM)
        validated_contradictions: list[StoryContradiction] = []

        # Deduplicate candidates on fact_type + src1_id + src2_id to keep DB clean
        seen_pairs = set()

        unvalidated = 0

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

            if res_resolution is None:
                unvalidated += 1
                continue

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
                validated_contradictions.append(contradiction)

        # This rewrites the story's contradictions wholesale, so it is only safe
        # when every candidate got an answer. If the validator was unreachable
        # for some of them, rewriting would delete contradictions confirmed by
        # an earlier run and replace them with a partial set — an outage would
        # silently erase good data. Leave the existing rows alone instead.
        if unvalidated:
            logger.warning(
                "Story %s: %d of %d contradiction candidates could not be validated; "
                "leaving existing contradictions untouched.",
                story_id,
                unvalidated,
                len(seen_pairs),
            )
            return []

        from sqlalchemy import delete

        await session.execute(
            delete(StoryContradiction).where(StoryContradiction.story_id == story_id)
        )

        for contradiction in validated_contradictions:
            session.add(contradiction)

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

                # 1. Actors Conflict — equivalence-aware, same as the batch path
                a1 = set(new_evt.actors or [])
                a2 = set(ext_evt.actors or [])
                if a1 and a2 and not sets_share_a_fact(a1, a2):
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
                if t1 and t2 and not sets_share_a_fact(t1, t2):
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

                # 3. Numbers Conflict — this path used bare `!=`, so "15" vs
                # "15.0" was a candidate. Same threshold as the batch path.
                num1 = new_evt.numbers or {}
                num2 = ext_evt.numbers or {}
                for k in num1.keys():
                    if k in num2 and numbers_conflict(num1[k], num2[k]):
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

        # This path only appends, so without checking the table it re-adds the
        # same source-pair contradiction on every incremental run — production
        # stories accumulated the identical description three times over.
        existing_res = await session.execute(
            select(StoryContradiction.fact_type, StoryContradiction.source_attribution).where(
                StoryContradiction.story_id == story_id
            )
        )
        for fact_type, attribution in existing_res.all():
            for s1 in attribution or {}:
                for s2 in attribution or {}:
                    if s1 != s2:
                        seen_pairs.add((fact_type, s1, s2))

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

            # Unlike the full pass this path only appends, so an unvalidated
            # candidate can simply be dropped without risking existing rows.
            if res_resolution is None:
                continue

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
