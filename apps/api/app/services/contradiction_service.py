"""Contradiction Service — structured fact contradiction detection between news sources.

Uses a hybrid approach:
1. Local heuristics flag potential conflicts in actors, targets, locations, times, or numbers.
2. If potential conflicts are found, an LLM checks them in context to ensure high precision (gating false positives).
3. Verified contradictions are persisted to the database.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.models import Article, ArticleEvent, Story, StoryContradiction, StoryArticle
from app.services.ai_service import _wait_for_synthesis_quota
from app.core.trace import track_llm_call

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
        self.gemini_enabled = False
        self._gemini_client = None
        api_key = settings.GEMINI_API_KEY_SYNTH or settings.GEMINI_API_KEY
        if api_key:
            try:
                from google import genai as google_genai

                self._gemini_client = google_genai.Client(api_key=api_key)
                self.gemini_enabled = True
            except ImportError:
                pass

        self._openai_client = None
        self.openai_enabled = False
        if settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI as OpenAIClient

                self._openai_client = OpenAIClient(api_key=settings.OPENAI_API_KEY)
                self.openai_enabled = True
            except Exception:
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
        """Call Gemini/OpenAI to verify if a candidate mismatch is a true contradiction."""
        prompt = (
            f"You are a factual contradiction validator for a news intelligence platform.\n"
            f"Compare these two conflicting reports of the same '{fact_type}' detail:\n"
            f"1. Source: {source1_name} reports: {val1}\n"
            f"2. Source: {source2_name} reports: {val2}\n\n"
            f"Context from the articles:\n{context[:3000]}\n\n"
            f"Determine if this is a true factual contradiction (e.g. Source A says Russia did it, Source B says Ukraine did it; or 15 dead vs 50 dead).\n"
            f"Note: Wording differences, translation variations, or subset relationships (e.g. '15 police officers' vs '15 people' or '15 dead' vs 'at least 10 dead') are NOT contradictions.\n\n"
            f"Respond in JSON matching this schema:\n"
            f'{{"is_contradiction": true/false, "description": "...", "confidence": 0.0-1.0}}'
        )

        try:
            from app.agents.contradiction_agent import check_contradiction
            agent_res = await check_contradiction(
                fact_type=fact_type,
                val1=str(val1),
                val2=str(val2),
                source1_name=source1_name,
                source2_name=source2_name,
                context=context
            )
            return ContradictionResolution(
                is_contradiction=agent_res.contradiction,
                description=agent_res.explanation,
                confidence=agent_res.confidence
            )
        except Exception as e:
            logger.warning("Agno Contradiction Agent failed: %s. Falling back.", e)

        if self.openai_enabled and self._openai_client:
            try:
                async with track_llm_call("openai", "gpt-4o-mini", "contradiction_detection", user_prompt=prompt) as call:
                    response = await self._openai_client.beta.chat.completions.parse(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a named entity resolution and contradiction checker.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        response_format=ContradictionResolution,
                        temperature=0.1,
                    )
                    call.response_text = response.choices[0].message.content or ""
                    if getattr(response, "usage", None):
                        call.input_tokens = response.usage.prompt_tokens or 0
                        call.output_tokens = response.usage.completion_tokens or 0
                    return response.choices[0].message.parsed
            except Exception as exc:
                logger.warning("OpenAI contradiction verification failed: %s", exc)

        # Fallback if AI disabled or failed
        desc = f"Mismatch on {fact_type}: {source1_name} reports '{val1}', while {source2_name} reports '{val2}'."
        return ContradictionResolution(
            is_contradiction=True,
            description=desc,
            confidence=0.70,
        )

    async def detect_and_save_contradictions(
        self, story_id: Any, session: AsyncSession
    ) -> list[StoryContradiction]:
        """Detect contradictions among the articles in a story and save them to the DB.

        First runs local heuristics, then validates with LLM.
        """
        # Fetch articles and their events
        stmt = (
            select(Article, ArticleEvent)
            .join(StoryArticle, StoryArticle.article_id == Article.id)
            .join(ArticleEvent, ArticleEvent.article_id == Article.id)
            .where(StoryArticle.story_id == story_id)
        )
        res = await session.execute(stmt)
        rows = list(res.all())

        if len(rows) < 2:
            return []

        # Build full text context for LLM disambiguation
        context_parts = []
        for art, evt in rows:
            src_name = art.source.name if art.source else "Unknown Source"
            context_parts.append(
                f"Source: {src_name}\nTitle: {art.title}\nContent: {art.description or ''}\n"
            )
        full_context = "\n".join(context_parts)

        # Candidate detection (pairwise comparison)
        candidates: list[dict[str, Any]] = []
        n_rows = len(rows)

        for i in range(n_rows):
            art1, evt1 = rows[i]
            src1_name = art1.source.name if art1.source else "Unknown Source"
            src1_id = str(art1.source_id)

            for j in range(i + 1, n_rows):
                art2, evt2 = rows[j]
                src2_name = art2.source.name if art2.source else "Unknown Source"
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
            await session.commit()

        return validated_contradictions


contradiction_service = ContradictionService()
