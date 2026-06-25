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

import hashlib
import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.event_taxonomy import canonicalize_event_type

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


class ExtractedArticleEntity(BaseModel):
    """A named entity extracted from the article alongside events."""

    value: str = Field(description="The entity text as it appears in the article")
    type: str = Field(
        description="Entity type: PERSON, ORG, COMPANY, COUNTRY, CITY, STATE, "
        "LOCATION, POLITICAL_PARTY, GOVERNMENT_BODY, MILITARY_UNIT, "
        "PRODUCT, TECHNOLOGY, LAW, AGREEMENT, WEAPON, SPORTS_TEAM, EVENT"
    )
    canonical_name: str | None = Field(
        default=None,
        description="Standardized canonical name (e.g., 'Rahul Gandhi' for 'Mr Gandhi')",
    )


class ArticleEventResponse(BaseModel):
    """Response schema for per-article event + entity extraction."""

    primary_event: ExtractedEvent = Field(description="The main event described in the article")
    secondary_events: list[ExtractedEvent] = Field(
        default_factory=list,
        description="Any secondary events mentioned in the article",
    )
    entities: list[ExtractedArticleEntity] = Field(
        default_factory=list,
        description="Named entities mentioned in the article",
    )


# ── Service ───────────────────────────────────────────────────────────────────


class EventService:
    """Extracts structured events from news article text using LLM."""

    def __init__(self) -> None:
        pass

    # ── Prompt ────────────────────────────────────────────────────────────────

    def _build_extraction_prompt(
        self,
        title: str,
        content: str,
        published_at: str | None = None,
    ) -> str:
        # Provide a representative sample of canonical types
        sample_types = [
            "ATTACK",
            "DETENTION",
            "ELECTION",
            "PROTEST",
            "AGREEMENT",
            "MERGER",
            "ACQUISITION",
            "POLICY",
            "SANCTIONS",
            "NATURAL_DISASTER",
            "WEATHER",
            "SPORTS",
            "DEATH",
            "LEGAL",
            "HEALTH",
            "DIPLOMACY",
            "MILITARY_OPERATION",
            "LAYOFF",
            "PRODUCT_LAUNCH",
            "INVESTMENT",
            "ACCIDENT",
            "SCANDAL",
            "LEGISLATION",
            "VIOLENCE",
            "IPO",
            "EARNINGS",
            "BANKRUPTCY",
            "SPACE",
            "AI_TECH",
            "DISCOVERY",
        ]

        return (
            "You are a structured event and entity extraction engine for news articles.\n"
            "Extract the PRIMARY EVENT described in the article AND all named entities.\n\n"
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
            "7. confidence = how confident you are in this extraction (0.0-1.0)\n"
            "8. entities = ALL named entities in the article (people, orgs, countries, cities, etc.)\n"
            "   - For each entity, provide: value (text as-is), type (PERSON/ORG/COUNTRY/etc.), canonical_name (standardized)\n"
            "   - Include entities from actors, targets, and location fields too\n\n"
            f"event_type must be one of: {', '.join(sample_types)}\n"
            "If none fit, use the closest match or a descriptive type.\n\n"
            "entity type must be one of: PERSON, ORG, COMPANY, COUNTRY, CITY, STATE, "
            "LOCATION, POLITICAL_PARTY, GOVERNMENT_BODY, MILITARY_UNIT, "
            "PRODUCT, TECHNOLOGY, LAW, AGREEMENT, WEAPON, SPORTS_TEAM, EVENT\n\n"
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
            '  "secondary_events": [],\n'
            '  "entities": [\n'
            '    {"value": "Joe Biden", "type": "PERSON", "canonical_name": "Joe Biden"},\n'
            '    {"value": "US", "type": "COUNTRY", "canonical_name": "United States"}\n'
            "  ]\n"
            "}\n"
        )

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
                evt["event_type"] = canonicalize_event_type(evt.get("event_type", "OTHER"))
                evt.setdefault("actors", [])
                evt.setdefault("targets", [])
                evt.setdefault("objects", [])
                evt.setdefault("location", "")
                evt.setdefault("event_time", None)
                evt.setdefault("numbers", {})
                evt.setdefault("confidence", 0.3)
                normalized_secondary.append(ExtractedEvent(**evt))

        # Normalize entities
        raw_entities = data.get("entities", [])
        if not isinstance(raw_entities, list):
            raw_entities = []
        normalized_entities = []
        for ent in raw_entities:
            if isinstance(ent, dict):
                val = str(ent.get("value", "")).strip()
                etype = str(ent.get("type", "PERSON")).strip().upper()
                if val:
                    normalized_entities.append(
                        ExtractedArticleEntity(
                            value=val,
                            type=etype,
                            canonical_name=ent.get("canonical_name"),
                        )
                    )

        return ArticleEventResponse(
            primary_event=ExtractedEvent(**primary),
            secondary_events=normalized_secondary,
            entities=normalized_entities,
        )

    # ── Mock fallback ─────────────────────────────────────────────────────────

    def _mock_extraction(self, title: str, content: str) -> ArticleEventResponse:
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
            entities=[],
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
            raise ValueError(
                "Cannot extract events from empty article (both title and content are missing)."
            )

        prompt = self._build_extraction_prompt(title, content, published_at)
        model = settings.SUMMARIZATION_MODEL or "gemini-2.5-flash-lite"

        from app.llm_gateway.request_manager import llm_gateway

        response = await llm_gateway.execute_request(
            model=model,
            stage="event_extraction",
            messages=[{"role": "user", "content": prompt}],
            response_format=ArticleEventResponse,
            temperature=0.1,
        )

        if response.parsed:
            return response.parsed

        data = json.loads(response.content)
        return self._normalize_response(data)

    async def detect_event_time_conflict(
        self,
        events: list[ExtractedEvent],
    ) -> bool:
        """Check if multiple articles' events have conflicting event times.

        This is NOT a contradiction in the journalistic sense — just a signal
        that different sources report different timings for the same event.
        """
        times = [e.event_time for e in events if e.event_time and e.event_time.strip()]
        if len(times) < 2:
            return False

        # Simple heuristic: if we have at least 2 distinct, non-null event times
        unique_times = set(times)
        return len(unique_times) > 1

    @staticmethod
    def compute_event_fingerprint(event: ExtractedEvent) -> str:
        """Compute a deterministic fingerprint hash for dedup-based pre-grouping.

        Hash of (event_type_canonical, sorted actors, sorted targets, location, event_date).
        Articles with identical fingerprints describe the same event.
        """
        from app.services.event_taxonomy import canonicalize_event_type

        canonical_type = canonicalize_event_type(event.event_type)
        actors = sorted(a.strip().lower() for a in event.actors if a.strip())
        targets = sorted(t.strip().lower() for t in event.targets if t.strip())
        location = event.location.strip().lower() if event.location else ""

        # Extract just the date portion from event_time for time-normalization
        event_date = ""
        if event.event_time:
            raw = event.event_time.strip()
            # Try ISO 8601 date extraction
            if len(raw) >= 10:
                event_date = raw[:10]  # YYYY-MM-DD

        parts = [
            canonical_type,
            "|".join(actors),
            "|".join(targets),
            location,
            event_date,
        ]
        fingerprint_str = "::".join(parts)
        return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()[:32]


event_service = EventService()
