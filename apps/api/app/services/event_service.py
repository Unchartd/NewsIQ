"""Event extraction service — structured event parsing from news articles.

Extracts WHO did WHAT to WHOM, WHERE, WHEN, and HOW from article text.
This runs PER-ARTICLE (not per-story) and stores results in article_events.

Key design decisions:
    - Separate LLM call from summarization — focused extraction is more accurate
    - Event time is explicitly separated from publication time
    - Uses event_taxonomy.py for canonicalization
    - Confidence scoring for clustering gate decisions

Rate limiting:
    Shares the same Gemini synthesis quota as ai_service.py.
    Uses the distributed Redis rate limiter in ai_service.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_combine,
    wait_exponential,
    wait_random,
)

from app.core.config import settings
from app.services.event_taxonomy import canonicalize_event_type, get_all_canonical_types
from app.core.trace import track_llm_call

logger = logging.getLogger(__name__)


# ── Pydantic schemas for structured event extraction ──────────────────────────


class ExtractedEvent(BaseModel):
    """Structured event extracted from a single news article."""

    event_type: str = Field(
        description="The type of event (e.g., ATTACK, ELECTION, MERGER, PROTEST)"
    )
    actors: list[str] = Field(
        default_factory=list,
        description="People/organizations that performed the action",
    )
    targets: list[str] = Field(
        default_factory=list,
        description="People/organizations/things affected by the action",
    )
    objects: list[str] = Field(
        default_factory=list,
        description="Key objects involved (weapons, documents, products, etc.)",
    )
    location: str = Field(
        default="",
        description="Where the event occurred (city, country, or specific place)",
    )
    event_time: str | None = Field(
        default=None,
        description=(
            "When the event actually happened (NOT when the article was published). "
            "Use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ) when possible, "
            "or natural language if exact time is unclear."
        ),
    )
    numbers: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Key numerical data: casualties, amounts, percentages, counts. "
            'Example: {"killed": 12, "injured": 30, "amount_usd": 5000000}'
        ),
    )
    confidence: float = Field(
        default=0.5,
        description="Confidence score 0.0-1.0 for this event extraction",
    )


class ArticleEventResponse(BaseModel):
    """Response schema for per-article event extraction."""

    primary_event: ExtractedEvent = Field(
        description="The main event described in the article"
    )
    secondary_events: list[ExtractedEvent] = Field(
        default_factory=list,
        description="Any secondary events mentioned in the article",
    )


# ── Service ───────────────────────────────────────────────────────────────────


class EventService:
    """Extracts structured events from news article text using LLM."""

    def __init__(self) -> None:
        self._gemini_client = None
        self.gemini_enabled = False
        api_key = settings.GEMINI_API_KEY_SYNTH or settings.GEMINI_API_KEY
        if api_key:
            try:
                from google import genai as google_genai

                self._gemini_client = google_genai.Client(api_key=api_key)
                self.gemini_enabled = True
                logger.info("EventService: Gemini configured for event extraction.")
            except ImportError:
                logger.error("google-genai not installed for EventService.")
            except Exception as exc:
                logger.error("EventService Gemini init failed: %s", exc)

        self._openai_client = None
        self.openai_enabled = False
        if settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI

                self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                self.openai_enabled = True
            except Exception as exc:
                logger.error("EventService OpenAI init failed: %s", exc)

    # ── Prompt ────────────────────────────────────────────────────────────────

    def _build_extraction_prompt(
        self,
        title: str,
        content: str,
        published_at: str | None = None,
    ) -> str:
        # Provide a representative sample of canonical types
        sample_types = [
            "ATTACK", "DETENTION", "ELECTION", "PROTEST", "AGREEMENT",
            "MERGER", "ACQUISITION", "POLICY", "SANCTIONS", "NATURAL_DISASTER",
            "WEATHER", "SPORTS", "DEATH", "LEGAL", "HEALTH",
            "DIPLOMACY", "MILITARY_OPERATION", "LAYOFF", "PRODUCT_LAUNCH",
            "INVESTMENT", "ACCIDENT", "SCANDAL", "LEGISLATION", "VIOLENCE",
            "IPO", "EARNINGS", "BANKRUPTCY", "SPACE", "AI_TECH", "DISCOVERY",
        ]

        return (
            "You are a structured event extraction engine for news articles.\n"
            "Extract the PRIMARY EVENT described in the article.\n\n"
            "CRITICAL RULES:\n"
            "1. event_time is WHEN THE EVENT HAPPENED, NOT when the article was published.\n"
            f"   The article was published at: {published_at or 'unknown'}. Do NOT use this as event_time.\n"
            "   If the article says 'yesterday', 'last week', 'on Monday', compute the actual date.\n"
            "   If the event time cannot be determined from the text, set event_time to null.\n"
            "2. actors = WHO performed the action (people, governments, companies, organizations)\n"
            "3. targets = WHO/WHAT was affected (victims, objects, countries affected)\n"
            "4. objects = KEY THINGS involved (weapons, documents, bills, products)\n"
            "5. location = WHERE it happened (be specific: city + country if available)\n"
            "6. numbers = any KEY NUMBERS mentioned (casualties, amounts, counts, percentages)\n"
            "7. confidence = how confident you are in this extraction (0.0-1.0)\n\n"
            f"event_type must be one of: {', '.join(sample_types)}\n"
            "If none fit, use the closest match or a descriptive type.\n\n"
            f"--- ARTICLE ---\n"
            f"Title: {title}\n"
            f"Content: {content[:6000]}\n"
            "--- END ---\n\n"
            "Respond with ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "primary_event": {\n'
            '    "event_type": "<canonical type>",\n'
            '    "actors": ["<actor1>", "<actor2>"],\n'
            '    "targets": ["<target1>"],\n'
            '    "objects": ["<object1>"],\n'
            '    "location": "<city, country>",\n'
            '    "event_time": "<ISO 8601 or null>",\n'
            '    "numbers": {"<key>": <value>},\n'
            '    "confidence": 0.85\n'
            "  },\n"
            '  "secondary_events": []\n'
            "}\n"
        )

    # ── Gemini extraction ─────────────────────────────────────────────────────

    async def _extract_with_gemini(
        self,
        title: str,
        content: str,
        published_at: str | None = None,
    ) -> ArticleEventResponse:
        """Extract events using Gemini structured output."""
        from app.services.ai_service import _wait_for_synthesis_quota
        from google.genai import types

        await _wait_for_synthesis_quota()

        prompt = self._build_extraction_prompt(title, content, published_at)
        model = settings.SUMMARIZATION_MODEL or "gemini-2.5-flash-lite"

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_combine(
                wait_exponential(multiplier=2, min=5, max=30),
                wait_random(min=0, max=2),
            ),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        async def _call():
            return await self._gemini_client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ArticleEventResponse,
                    temperature=0.1,
                ),
            )

        async with track_llm_call("gemini", model, "event_extraction", user_prompt=prompt) as call:
            response = await _call()
            call.response_text = response.text
            if getattr(response, "usage_metadata", None):
                call.input_tokens = response.usage_metadata.prompt_token_count or 0
                call.output_tokens = response.usage_metadata.candidates_token_count or 0
            raw_text = response.text

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error("Gemini event extraction returned non-JSON: %.200s", raw_text)
            raise

        return self._normalize_response(data)

    # ── OpenAI extraction ─────────────────────────────────────────────────────

    async def _extract_with_openai(
        self,
        title: str,
        content: str,
        published_at: str | None = None,
    ) -> ArticleEventResponse:
        """Extract events using OpenAI structured output."""
        prompt = self._build_extraction_prompt(title, content, published_at)

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        async def _call():
            return await self._openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a structured event extraction engine for news articles.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=ArticleEventResponse,
                temperature=0.1,
            )

        async with track_llm_call("openai", "gpt-4o-mini", "event_extraction", user_prompt=prompt) as call:
            response = await _call()
            call.response_text = response.choices[0].message.content or ""
            if getattr(response, "usage", None):
                call.input_tokens = response.usage.prompt_tokens or 0
                call.output_tokens = response.usage.completion_tokens or 0
            
            return response.choices[0].message.parsed

    # ── Response normalization ────────────────────────────────────────────────

    def _normalize_response(self, data: dict[str, Any]) -> ArticleEventResponse:
        """Normalize and canonicalize the LLM response."""
        primary = data.get("primary_event", {})
        if not isinstance(primary, dict):
            primary = {}

        # Canonicalize event type using taxonomy
        raw_type = primary.get("event_type", "OTHER")
        primary["event_type"] = canonicalize_event_type(raw_type)

        # Ensure required fields have defaults
        primary.setdefault("actors", [])
        primary.setdefault("targets", [])
        primary.setdefault("objects", [])
        primary.setdefault("location", "")
        primary.setdefault("event_time", None)
        primary.setdefault("numbers", {})
        primary.setdefault("confidence", 0.5)

        # Clamp confidence to [0.0, 1.0]
        primary["confidence"] = max(0.0, min(1.0, float(primary.get("confidence", 0.5))))

        # Clean string lists
        for field in ("actors", "targets", "objects"):
            val = primary.get(field, [])
            if isinstance(val, str):
                primary[field] = [val]
            elif isinstance(val, list):
                primary[field] = [str(v).strip() for v in val if v]

        # Normalize secondary events
        secondary = data.get("secondary_events", [])
        if not isinstance(secondary, list):
            secondary = []
        normalized_secondary = []
        for evt in secondary:
            if isinstance(evt, dict):
                evt["event_type"] = canonicalize_event_type(
                    evt.get("event_type", "OTHER")
                )
                evt.setdefault("actors", [])
                evt.setdefault("targets", [])
                evt.setdefault("objects", [])
                evt.setdefault("location", "")
                evt.setdefault("event_time", None)
                evt.setdefault("numbers", {})
                evt.setdefault("confidence", 0.3)
                normalized_secondary.append(ExtractedEvent(**evt))

        return ArticleEventResponse(
            primary_event=ExtractedEvent(**primary),
            secondary_events=normalized_secondary,
        )

    # ── Mock fallback ─────────────────────────────────────────────────────────

    def _mock_extraction(
        self, title: str, content: str
    ) -> ArticleEventResponse:
        """Deterministic mock for local dev — clearly marked."""
        return ArticleEventResponse(
            primary_event=ExtractedEvent(
                event_type="OTHER",
                actors=["[Mock] Unknown Actor"],
                targets=[],
                objects=[],
                location="[Mock] Unknown Location",
                event_time=None,
                numbers={},
                confidence=0.1,
            ),
            secondary_events=[],
        )

    # ── Public API ────────────────────────────────────────────────────────────

    async def extract_events(
        self,
        title: str,
        content: str,
        published_at: str | None = None,
    ) -> ArticleEventResponse:
        """Extract structured events from a news article.

        Fallback chain: Gemini → OpenAI → mock.

        Args:
            title: Article headline
            content: Full article text
            published_at: ISO 8601 publication timestamp (NOT used as event_time)
        """
        if not title and not content:
            return self._mock_extraction("", "")

        if self.gemini_enabled:
            try:
                return await self._extract_with_gemini(title, content, published_at)
            except Exception as exc:
                logger.error("Gemini event extraction failed: %s — trying OpenAI.", exc)

        if self.openai_enabled and self._openai_client:
            try:
                return await self._extract_with_openai(title, content, published_at)
            except Exception as exc:
                logger.error("OpenAI event extraction failed: %s — using mock.", exc)

        logger.warning("All event extraction providers failed — using mock.")
        return self._mock_extraction(title, content)

    async def detect_event_time_conflict(
        self,
        events: list[ExtractedEvent],
    ) -> bool:
        """Check if multiple articles' events have conflicting event times.

        This is NOT a contradiction in the journalistic sense — just a signal
        that different sources report different timings for the same event.
        """
        times = [
            e.event_time for e in events
            if e.event_time and e.event_time.strip()
        ]
        if len(times) < 2:
            return False

        # Simple heuristic: if we have at least 2 distinct, non-null event times
        unique_times = set(times)
        return len(unique_times) > 1


event_service = EventService()
