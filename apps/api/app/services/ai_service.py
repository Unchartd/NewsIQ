"""AI service — story summarization, timeline, and source difference engine.

Uses the new google.genai SDK (google-genai>=1.16.0) with OpenAI fallback.

Priority:
    1. Google Gemini (gemini-2.5-flash-lite) via google.genai async client
    2. OpenAI (gpt-4o-mini) via structured output
    3. Deterministic mock — clearly prefixed [Mock] — for local dev only

Rate limiting: The free-tier gemini-2.5-flash-lite model has strict RPM limits.
We use tenacity with aggressive back-off (up to 60s) to handle 429s gracefully.
Celery worker concurrency is set to 2 to limit concurrent synthesis calls.
"""

import asyncio
import json
import logging
import time
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
    wait_combine,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis key for distributed synthesis rate limiting across all Celery worker processes
_SYNTHESIS_REDIS_KEY = "newsiq:synthesis:last_call"
_SYNTHESIS_MIN_INTERVAL_S = 8.0  # seconds between synthesis calls = ~7.5 RPM (free tier: 10 RPM)


async def _wait_for_synthesis_quota() -> None:
    """Distributed rate limiter using Redis.

    Ensures a minimum interval between Gemini synthesis calls across ALL worker
    processes. Without this, 2 concurrent workers both call generateContent
    simultaneously and one always gets 429.

    Uses Redis GET/SET with a float timestamp. Not perfectly atomic but good
    enough for this use case — worst case two calls overlap once, but the retry
    with backoff will handle it.
    """
    try:
        import redis as redis_lib
        import time

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        last_str = r.get(_SYNTHESIS_REDIS_KEY)
        if last_str:
            elapsed = time.time() - float(last_str)
            if elapsed < _SYNTHESIS_MIN_INTERVAL_S:
                wait_s = _SYNTHESIS_MIN_INTERVAL_S - elapsed
                logger.debug("Synthesis rate limiter: sleeping %.1fs", wait_s)
                await asyncio.sleep(wait_s)
        # Record this call's start time
        r.set(_SYNTHESIS_REDIS_KEY, str(time.time()), ex=60)
    except Exception as exc:
        # Non-fatal — fall through without throttling if Redis is down
        logger.warning("Synthesis rate limiter Redis error (non-fatal): %s", exc)

# Canonical category slugs the AI must choose from
CATEGORY_SLUGS = [
    "politics",
    "world",
    "business",
    "technology",
    "sports",
    "entertainment",
    "lifestyle",
    "travel",
    "education",
    "health",
    "science",
    "weather",
]


# ── Response schemas (used as structured output contracts for both Gemini & OpenAI) ──


class TimelineEventSchema(BaseModel):
    date: str = Field(description="Date or time of the event, e.g. YYYY-MM-DD or time of day")
    description: str = Field(description="Summary of what happened at this point in the timeline")


class SourceDifferenceSchema(BaseModel):
    source_name: str = Field(description="Name of the news source/publisher, e.g. Reuters, BBC")
    unique_information: str = Field(
        description="Details mentioned ONLY by this source, or empty string"
    )
    missing_information: str = Field(
        description="Key details omitted by this source that others covered, or empty string"
    )
    contradictions: str = Field(
        description="Any factual contradictions or conflicting claims made by this source, or empty string"
    )


class StoryAIResponse(BaseModel):
    headline: str = Field(
        description="A highly neutral, objective, and non-clickbait headline summarizing the event"
    )
    one_line_summary: str = Field(description="A concise 1-sentence summary of the story")
    short_summary: str = Field(description="A short 1-paragraph summary (3-4 sentences)")
    detailed_summary: str = Field(
        description="A detailed multi-paragraph summary covering all angles and context"
    )
    key_facts: list[str] = Field(description="List of 3 to 6 key objective bullet points of fact")
    category: str = Field(
        description=(
            f"The single best-matching category slug for this story. "
            f"Must be one of: {', '.join(CATEGORY_SLUGS)}"
        )
    )
    timeline: list[TimelineEventSchema] = Field(
        description="Chronological timeline of events leading up to and during the story"
    )
    differences: list[SourceDifferenceSchema] = Field(
        description="Analysis of differences, biases, omissions, or contradictions per news source"
    )


class AIService:
    """Story analysis using Gemini (new google.genai SDK) with OpenAI fallback."""

    def __init__(self) -> None:
        # ── Gemini (new google.genai SDK) ──────────────────────────────────────
        self.gemini_enabled = False
        self._gemini_client = None
        api_key = settings.GEMINI_API_KEY_SYNTH or settings.GEMINI_API_KEY
        if api_key:
            try:
                from google import genai as google_genai

                self._gemini_client = google_genai.Client(api_key=api_key)
                self.gemini_enabled = True
                logger.info(
                    "Google Gemini AI configured: model=%s", settings.SUMMARIZATION_MODEL
                )
            except ImportError:
                logger.error(
                    "google-genai package not installed. "
                    "Run: pip install google-genai>=1.16.0"
                )
            except Exception as exc:
                logger.error("Failed to configure Google Gemini AI client: %s", exc)
        else:
            logger.warning("GEMINI_API_KEY_SYNTH or GEMINI_API_KEY is not set. Gemini AI is disabled.")

        # ── OpenAI fallback ────────────────────────────────────────────────────
        self.openai_enabled = False
        self.openai_client: AsyncOpenAI | None = None
        if settings.OPENAI_API_KEY:
            try:
                self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                self.openai_enabled = True
                logger.info("OpenAI AI fallback configured.")
            except Exception as exc:
                logger.error("Failed to configure OpenAI client: %s", exc)
        else:
            logger.debug("OPENAI_API_KEY not set — OpenAI AI fallback disabled.")

    # ── Prompt builder ─────────────────────────────────────────────────────────

    def _build_prompt(self, articles: list[dict[str, Any]]) -> str:
        articles_text = ""
        for i, art in enumerate(articles):
            articles_text += (
                f"--- ARTICLE {i + 1} ---\n"
                f"Source: {art.get('source_name', 'Unknown')}\n"
                f"Published: {art.get('published_at', 'Unknown')}\n"
                f"Title: {art.get('title', 'No Title')}\n"
                f"Content: {art.get('content', '')[:3000]}\n\n"
            )

        # Embed the exact JSON schema in the prompt so the model produces the right structure
        schema = (
            '{\n'
            '  "headline": "<neutral headline>",\n'
            '  "one_line_summary": "<1-sentence summary>",\n'
            '  "short_summary": "<1-paragraph 3-4 sentence summary>",\n'
            '  "detailed_summary": "<multi-paragraph detailed summary>",\n'
            '  "key_facts": ["fact1", "fact2", "fact3"],\n'
            '  "category": "<one of: politics, world, business, technology, sports, entertainment, lifestyle, travel, education, health, science, weather>",\n'
            '  "timeline": [{"date": "YYYY-MM-DD", "description": "<event>"}],\n'
            '  "differences": [{"source_name": "<source>", "unique_information": "<text>", "missing_information": "<text>", "contradictions": "<text>"}]\n'
            '}'
        )

        return (
            "You are an objective, expert news intelligence analyst.\n"
            "Analyze the following articles about a single news event. "
            "Your output must be completely neutral, free of editorializing, clickbait, or political bias.\n\n"
            f"{articles_text}\n"
            "Synthesize this information into a single cohesive story.\n"
            f"For the 'category' field, choose exactly one slug from: {', '.join(CATEGORY_SLUGS)}.\n"
            "For timeline dates, use ISO 8601 format (YYYY-MM-DD) whenever possible.\n\n"
            "Respond with ONLY a valid JSON object matching this exact schema (no markdown, no code blocks):\n"
            f"{schema}"
        )

    # ── Gemini analysis (new SDK — async generate_content) ────────────────────

    async def _analyze_with_gemini(self, articles: list[dict[str, Any]]) -> StoryAIResponse:
        """Use Gemini via the new google.genai async client for structured story synthesis.

        Rate limit handling:
        - Free tier: ~10 RPM for gemini-2.5-flash-lite
        - Redis distributed rate limiter: 1 call per 8s across all workers (~7.5 RPM)
        - Tenacity retry: 5 attempts, exponential+jitter backoff up to 60s
        - Model fallback chain: tries multiple models when one hits daily quota
        """
        # Enforce global rate limit across all Celery worker processes via Redis
        await _wait_for_synthesis_quota()

        from google.genai import types

        prompt = self._build_prompt(articles)
        client = self._gemini_client

        # Model priority chain — if primary hits daily quota, try alternatives
        # Order: best quality → lowest quota risk
        primary = settings.SUMMARIZATION_MODEL or "gemini-2.5-flash-lite"
        model_chain = list(dict.fromkeys([
            primary,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash-lite",
        ]))

        last_exc: Exception | None = None
        for model in model_chain:
            try:
                @retry(
                    stop=stop_after_attempt(3),
                    wait=wait_combine(
                        wait_exponential(multiplier=2, min=5, max=30),
                        wait_random(min=0, max=2),
                    ),
                    retry=retry_if_exception_type(Exception),
                    reraise=True,
                )
                async def _call(m: str = model) -> str:
                    response = await client.aio.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=StoryAIResponse,
                            temperature=0.1,
                        ),
                    )
                    return response.text

                raw_text = await _call()

                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError as exc:
                    logger.error("Gemini (%s) returned non-JSON: %.200s", model, raw_text)
                    raise exc

                # Normalise field names — the model sometimes uses camelCase or nests objects
                data = self._normalize_gemini_response(data)
                if data.get("category") not in CATEGORY_SLUGS:
                    data["category"] = "world"

                try:
                    result = StoryAIResponse(**data)
                    if model != primary:
                        logger.info("Synthesis succeeded using fallback model: %s", model)
                    return result
                except Exception as exc:
                    logger.error(
                        "Gemini (%s) response failed Pydantic validation: %s\nRaw (first 500 chars): %.500s",
                        model, exc, raw_text,
                    )
                    raise exc

            except Exception as exc:
                err_str = str(exc)
                # Daily quota exhausted (RESOURCE_EXHAUSTED) — try next model
                if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                    logger.warning(
                        "Gemini model %s quota exhausted — trying next model in chain.", model
                    )
                    last_exc = exc
                    continue
                # Other errors (invalid API key, network) — don't try next model
                raise

        # All models exhausted
        logger.error("All Gemini models hit quota limits. Chain: %s", model_chain)
        raise last_exc or RuntimeError("All Gemini synthesis models exhausted")


    def _normalize_gemini_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize Gemini's JSON response to match StoryAIResponse schema.

        Handles common variations: camelCase keys, nested structures,
        missing optional fields, etc.
        """
        # Normalize camelCase to snake_case for common fields
        key_map = {
            "oneLineSummary": "one_line_summary",
            "shortSummary": "short_summary",
            "detailedSummary": "detailed_summary",
            "keyFacts": "key_facts",
        }
        for old_key, new_key in key_map.items():
            if old_key in data and new_key not in data:
                data[new_key] = data.pop(old_key)

        # Ensure key_facts is a list of strings
        if "key_facts" in data:
            kf = data["key_facts"]
            if isinstance(kf, str):
                data["key_facts"] = [kf]
            elif isinstance(kf, list):
                data["key_facts"] = [str(f) for f in kf]
        else:
            data["key_facts"] = []

        # Normalize timeline entries
        if "timeline" in data and isinstance(data["timeline"], list):
            normalized = []
            for item in data["timeline"]:
                if isinstance(item, dict):
                    normalized.append({
                        "date": str(item.get("date", item.get("time", "Unknown"))),
                        "description": str(item.get("description", item.get("event", ""))),
                    })
            data["timeline"] = normalized
        else:
            data["timeline"] = []

        # Normalize differences entries
        if "differences" in data and isinstance(data["differences"], list):
            normalized = []
            for item in data["differences"]:
                if isinstance(item, dict):
                    normalized.append({
                        "source_name": str(item.get("source_name", item.get("source", "Unknown"))),
                        "unique_information": str(item.get("unique_information", item.get("unique", ""))),
                        "missing_information": str(item.get("missing_information", item.get("missing", ""))),
                        "contradictions": str(item.get("contradictions", "")),
                    })
            data["differences"] = normalized
        else:
            data["differences"] = []

        # Ensure required string fields have defaults
        for field in ("headline", "one_line_summary", "short_summary", "detailed_summary"):
            if field not in data or not data[field]:
                data[field] = ""

        return data

    # ── OpenAI fallback analysis ───────────────────────────────────────────────

    async def _analyze_with_openai(self, articles: list[dict[str, Any]]) -> StoryAIResponse:
        """Use OpenAI gpt-4o-mini with structured output as fallback."""
        prompt = self._build_prompt(articles)

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        async def _call():
            return await self.openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an objective, expert news intelligence analyst.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=StoryAIResponse,
                temperature=0.1,
            )

        response = await _call()
        data = response.choices[0].message.parsed
        if data.category not in CATEGORY_SLUGS:
            data.category = "world"
        return data

    # ── Mock fallback ──────────────────────────────────────────────────────────

    def _generate_mock_response(self, articles: list[dict[str, Any]]) -> StoryAIResponse:
        """Mock fallback — clearly prefixed [Mock] so it's never confused with real AI output."""
        primary = articles[0] if articles else {"title": "Global Event", "content": ""}
        title = primary.get("title") or "Major News Event"
        sources = list(set(a.get("source_name", "Unknown Source") for a in articles))

        mock_diffs = [
            SourceDifferenceSchema(
                source_name=src,
                unique_information=f"{src} highlighted specific local context.",
                missing_information=f"{src} omitted international diplomatic responses.",
                contradictions="",
            )
            for src in sources
        ]

        return StoryAIResponse(
            headline=f"[Mock] {title}",
            one_line_summary=(
                f"[Mock] Story involving {len(articles)} articles from {', '.join(sources)}."
            ),
            short_summary=(
                f"[Mock] Short summary. Coverage from {', '.join(sources)}. "
                "Key event with immediate impacts and ongoing developments."
            ),
            detailed_summary=(
                f"[Mock] Detailed summary.\n\n"
                f"Background: Reports from {sources[0] if sources else 'Reuters'} on the incident.\n\n"
                "Impact: Market indices fluctuated; analysts released preliminary reports.\n\n"
                "Outlook: Investigators expect results within days."
            ),
            key_facts=[
                f"[Mock] Reported by {sources[0] if sources else 'Reuters'} with {len(sources)} sources.",
                "[Mock] Regulatory scrutiny and economic reaction followed.",
                "[Mock] Investigation underway.",
            ],
            category="world",
            timeline=[
                TimelineEventSchema(date="08:00 AM UTC", description="[Mock] Initial report."),
                TimelineEventSchema(
                    date="02:00 PM UTC", description="[Mock] Press conference held."
                ),
            ],
            differences=mock_diffs,
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    async def analyze_story(self, articles: list[dict[str, Any]]) -> StoryAIResponse:
        """Analyze a cluster of articles and produce a structured story.

        Fallback chain: Gemini → OpenAI → mock.
        """
        if not articles:
            raise ValueError("No articles provided for AI analysis.")

        if self.gemini_enabled:
            try:
                logger.info("Analyzing story with Gemini (%d articles).", len(articles))
                return await self._analyze_with_gemini(articles)
            except Exception as exc:
                logger.error("Gemini story analysis failed: %s — trying OpenAI.", exc)

        if self.openai_enabled and self.openai_client:
            try:
                logger.info("Analyzing story with OpenAI fallback (%d articles).", len(articles))
                return await self._analyze_with_openai(articles)
            except Exception as exc:
                logger.error("OpenAI story analysis failed: %s — using mock.", exc)

        logger.warning("All AI providers failed — using mock response.")
        return self._generate_mock_response(articles)


ai_service = AIService()
