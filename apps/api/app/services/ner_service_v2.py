"""Enhanced NER service — LLM-based entity extraction with 25+ entity types.

Replaces the old spaCy-only NER with a two-pass approach:
    1. LLM (Gemini/OpenAI) for high-accuracy, context-aware extraction
    2. spaCy fallback with enhanced post-processing rules

Design principles:
    - Context-aware: "MoU" → AGREEMENT, "Andhra Pradesh" → STATE
    - 25+ entity types vs the old 4 (PERSON, ORG, LOCATION, EVENT)
    - Confidence scoring per entity
    - Deduplication and canonicalization
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Supported Entity Types ────────────────────────────────────────────────────

ENTITY_TYPES = [
    "PERSON",
    "ORG",
    "COMPANY",
    "COUNTRY",
    "CITY",
    "STATE",
    "PLACE",
    "LOCATION",
    "EVENT",
    "AGREEMENT",
    "LAW",
    "PRODUCT",
    "TECHNOLOGY",
    "POLITICAL_PARTY",
    "WEAPON",
    "SHIP",
    "AIRCRAFT",
    "DATE",
    "TIME",
    "MONEY",
    "PERCENTAGE",
    "CRYPTO",
    "SPORTS_TEAM",
    "DISEASE",
    "GOVERNMENT_BODY",
    "MILITARY_UNIT",
]


# ── Pydantic schema ──────────────────────────────────────────────────────────


class ExtractedEntity(BaseModel):
    """A single named entity extracted from text."""

    value: str = Field(description="The entity text as it appears in the article")
    type: str = Field(description=f"Entity type, one of: {', '.join(ENTITY_TYPES)}")
    canonical_name: str | None = Field(
        default=None,
        description="Standardized/canonical name (e.g., 'Rahul Gandhi' for 'Mr Gandhi')",
    )
    confidence: float = Field(
        default=0.8,
        description="Confidence score 0.0-1.0",
    )


class EntityExtractionResponse(BaseModel):
    """Response from entity extraction."""

    entities: list[ExtractedEntity] = Field(default_factory=list)


# ── Known entity patterns (rules-based pre-classification) ───────────────────

# Agreements and legal terms often misclassified
AGREEMENT_PATTERNS: set[str] = {
    "mou",
    "memorandum of understanding",
    "treaty",
    "accord",
    "pact",
    "convention",
    "protocol",
    "charter",
    "declaration",
    "framework agreement",
    "free trade agreement",
    "fta",
    "bilateral agreement",
    "ceasefire agreement",
    "peace agreement",
    "arms deal",
    "nuclear deal",
    "trade deal",
    "paris agreement",
    "geneva convention",
    "camp david accords",
    "abraham accords",
    "oslo accords",
    "minsk agreement",
}

LAW_PATTERNS: set[str] = {
    "act",
    "bill",
    "amendment",
    "statute",
    "regulation",
    "ordinance",
    "executive order",
    "directive",
    "resolution",
    "article",
}

POLITICAL_PARTY_KEYWORDS: set[str] = {
    "party",
    "congress",
    "bjp",
    "democratic",
    "republican",
    "labour",
    "conservative",
    "liberal",
    "green party",
    "aap",
    "tmc",
    "communist",
    "socialist",
    "peoples party",
}

# Indian states — commonly misclassified as PERSON
INDIAN_STATES: set[str] = {
    "andhra pradesh",
    "arunachal pradesh",
    "assam",
    "bihar",
    "chhattisgarh",
    "goa",
    "gujarat",
    "haryana",
    "himachal pradesh",
    "jharkhand",
    "karnataka",
    "kerala",
    "madhya pradesh",
    "maharashtra",
    "manipur",
    "meghalaya",
    "mizoram",
    "nagaland",
    "odisha",
    "punjab",
    "rajasthan",
    "sikkim",
    "tamil nadu",
    "telangana",
    "tripura",
    "uttar pradesh",
    "uttarakhand",
    "west bengal",
    "jammu and kashmir",
    "ladakh",
}

# US states
US_STATES: set[str] = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
}

ALL_STATES: set[str] = INDIAN_STATES | US_STATES

# University indicators
UNIVERSITY_INDICATORS: set[str] = {
    "university",
    "college",
    "institute",
    "school of",
    "academy",
    "polytechnic",
    "iit",
    "iim",
    "mit",
    "harvard",
    "oxford",
    "cambridge",
    "stanford",
    "yale",
    "princeton",
}


# ── Enhanced NER Service ──────────────────────────────────────────────────────


class NERServiceV2:
    """Enhanced Named Entity Recognition with LLM primary + spaCy fallback.

    Key improvements over v1:
    - 25+ entity types (vs 4)
    - LLM-based extraction for context awareness
    - Rules-based post-processing for known patterns
    - Confidence scoring
    - Deduplication
    """

    def __init__(self) -> None:
        # ── spaCy fallback ────────────────────────────────────────────────────
        self._nlp = None
        try:
            import spacy

            # Try loading larger model first, fall back to small
            for model_name in ("en_core_web_lg", "en_core_web_sm"):
                try:
                    self._nlp = spacy.load(model_name)
                    logger.info("NERServiceV2: Loaded spaCy model '%s'", model_name)
                    break
                except OSError:
                    continue
            if not self._nlp:
                logger.warning("NERServiceV2: No spaCy model available.")
        except ImportError:
            logger.warning("NERServiceV2: spaCy not installed.")

    # ── LLM Prompt ────────────────────────────────────────────────────────────

    def _build_ner_prompt(self, text: str) -> str:
        return (
            "Extract ALL named entities from the following news text.\n"
            "For EACH entity, provide:\n"
            "- value: the entity text as it appears\n"
            "- type: entity type from this list:\n"
            f"  {', '.join(ENTITY_TYPES)}\n"
            "- canonical_name: the standardized/full name (e.g., 'Rahul Gandhi' for 'Mr Gandhi')\n"
            "- confidence: 0.0-1.0\n\n"
            "CRITICAL RULES:\n"
            "1. 'MoU' or 'Memorandum of Understanding' → type: AGREEMENT\n"
            "2. Indian states like 'Andhra Pradesh', 'Tamil Nadu' → type: STATE\n"
            "3. US states like 'California', 'Texas' → type: STATE\n"
            "4. Universities and colleges → type: ORG\n"
            "5. Political parties → type: POLITICAL_PARTY\n"
            "6. Countries → type: COUNTRY\n"
            "7. Cities → type: CITY\n"
            "8. Companies/corporations → type: COMPANY\n"
            "9. Government bodies (Supreme Court, Parliament, Congress) → type: GOVERNMENT_BODY\n"
            "10. Do NOT classify organizations, places, or agreements as PERSON.\n\n"
            f"--- TEXT ---\n{text[:8000]}\n--- END ---\n\n"
            "Respond with ONLY valid JSON:\n"
            '{"entities": [{"value": "...", "type": "...", "canonical_name": "...", "confidence": 0.9}]}\n'
        )

    # LLM extraction routed through gateway in extract_entities()

    # ── spaCy fallback + rules ────────────────────────────────────────────────

    def _extract_with_spacy(self, text: str) -> list[ExtractedEntity]:
        """Enhanced spaCy extraction with post-processing rules."""
        if not self._nlp:
            return self._extract_with_rules(text)

        entities: list[ExtractedEntity] = []
        seen: set[str] = set()

        try:
            doc = self._nlp(text[:100000])
            for ent in doc.ents:
                val = ent.text.strip().replace("\n", " ")
                if len(val) < 2 or val in seen:
                    continue
                seen.add(val)

                # Enhanced label mapping with rules
                entity_type = self._reclassify_spacy_entity(val, ent.label_)
                if entity_type:
                    entities.append(
                        ExtractedEntity(
                            value=val,
                            type=entity_type,
                            canonical_name=None,
                            confidence=0.6,
                        )
                    )
        except Exception as e:
            logger.error("spaCy extraction failed: %s", e)
            return self._extract_with_rules(text)

        return entities

    def _reclassify_spacy_entity(self, value: str, spacy_label: str) -> str | None:
        """Reclassify spaCy entities using rules for known patterns."""
        val_lower = value.lower().strip()

        # ── Rules-based reclassification ──────────────────────────────────────

        # Check agreements
        if val_lower in AGREEMENT_PATTERNS:
            return "AGREEMENT"
        for pattern in AGREEMENT_PATTERNS:
            if pattern in val_lower:
                return "AGREEMENT"

        # Check states
        if val_lower in ALL_STATES:
            return "STATE"

        # Check universities → ORG
        for indicator in UNIVERSITY_INDICATORS:
            if indicator in val_lower:
                return "ORG"

        # Check political parties
        for keyword in POLITICAL_PARTY_KEYWORDS:
            if keyword in val_lower:
                return "POLITICAL_PARTY"

        # Check laws
        for pattern in LAW_PATTERNS:
            if val_lower.endswith(f" {pattern}") or val_lower.startswith(f"{pattern} "):
                return "LAW"

        # ── Standard spaCy label mapping ──────────────────────────────────────

        label_map = {
            "PERSON": "PERSON",
            "ORG": "ORG",
            "GPE": "COUNTRY",  # Default GPE to COUNTRY, refined below
            "LOC": "LOCATION",
            "EVENT": "EVENT",
            "PRODUCT": "PRODUCT",
            "WORK_OF_ART": "PRODUCT",
            "LAW": "LAW",
            "MONEY": "MONEY",
            "PERCENT": "PERCENTAGE",
            "DATE": "DATE",
            "TIME": "TIME",
            "NORP": "POLITICAL_PARTY",  # Nationalities, religious, political groups
            "FAC": "PLACE",  # Facilities
            "LANGUAGE": None,  # Skip languages
            "QUANTITY": None,
            "ORDINAL": None,
            "CARDINAL": None,
        }

        entity_type = label_map.get(spacy_label)
        if entity_type is None:
            return None  # Skip this entity

        # Refine GPE: is it a city, state, or country?
        if spacy_label == "GPE":
            if val_lower in ALL_STATES:
                return "STATE"
            # Could be further refined with a cities database
            # For now, GPE → COUNTRY for well-known countries
            return "COUNTRY"

        return entity_type

    def _extract_with_rules(self, text: str) -> list[ExtractedEntity]:
        """Last-resort regex-based extraction with improved heuristics."""
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()

        if not text:
            return entities

        # Extract capitalized word sequences
        pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        matches = re.findall(pattern, text[:50000])

        for match in matches:
            if match in seen or len(match) < 3:
                continue
            seen.add(match)

            lower = match.lower()

            # Apply rules
            if lower in ALL_STATES:
                entities.append(ExtractedEntity(value=match, type="STATE", confidence=0.7))
            elif lower in AGREEMENT_PATTERNS:
                entities.append(ExtractedEntity(value=match, type="AGREEMENT", confidence=0.6))
            elif any(ind in lower for ind in UNIVERSITY_INDICATORS):
                entities.append(ExtractedEntity(value=match, type="ORG", confidence=0.6))
            elif any(kw in lower for kw in POLITICAL_PARTY_KEYWORDS):
                entities.append(
                    ExtractedEntity(value=match, type="POLITICAL_PARTY", confidence=0.5)
                )
            else:
                # Don't default to PERSON — leave as ORG if 3+ words, PERSON if 2 words
                if len(match.split()) >= 3:
                    entities.append(ExtractedEntity(value=match, type="ORG", confidence=0.3))
                elif len(match.split()) == 2:
                    entities.append(ExtractedEntity(value=match, type="PERSON", confidence=0.3))
                # Single words: skip (too ambiguous without context)

        return entities

    # ── Normalization ─────────────────────────────────────────────────────────

    def _normalize_entities(self, entities_raw: list[dict[str, Any]]) -> list[ExtractedEntity]:
        """Normalize and deduplicate extracted entities."""
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()

        for raw in entities_raw:
            if not isinstance(raw, dict):
                continue

            value = str(raw.get("value", "")).strip()
            if not value or len(value) < 2:
                continue

            # Deduplicate
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)

            # Validate entity type
            entity_type = str(raw.get("type", "")).upper().strip()
            if entity_type not in ENTITY_TYPES:
                # Try to reclassify
                entity_type = self._reclassify_spacy_entity(value, entity_type) or "ORG"

            # Apply post-processing rules (override LLM if rules are confident)
            val_lower = value.lower()
            if val_lower in ALL_STATES:
                entity_type = "STATE"
            elif val_lower in AGREEMENT_PATTERNS or any(p in val_lower for p in AGREEMENT_PATTERNS):
                entity_type = "AGREEMENT"

            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))

            entities.append(
                ExtractedEntity(
                    value=value,
                    type=entity_type,
                    canonical_name=raw.get("canonical_name"),
                    confidence=confidence,
                )
            )

        return entities

    # ── Public API ────────────────────────────────────────────────────────────

    async def extract_entities(self, text: str) -> list[dict[str, str]]:
        """Extract entities from text. Returns list of dicts for backward compatibility.

        Returns: [{"value": "Entity Name", "type": "PERSON", "confidence": "0.9"}]
        """
        if not text or not text.strip():
            return []

        from app.core.trace import story_id_ctx

        story_id = story_id_ctx.get("")

        try:
            response: Any
            from app.ai.gateway import ai_gateway

            response = await ai_gateway.generate_stage(
                stage="entity_extraction",
                prompt_variables={"text": text},
                schema=EntityExtractionResponse,
                story_id=story_id,
            )

            entities_raw = []
            if response.parsed:
                entities_raw = [e.model_dump() for e in response.parsed.entities]
            else:
                try:
                    data = json.loads(response.content)
                    entities_raw = data.get("entities", [])
                except Exception:
                    pass

            if entities_raw:
                normalized = self._normalize_entities(entities_raw)
                return [
                    {
                        "value": e.value,
                        "type": e.type,
                        "canonical_name": e.canonical_name or e.value,
                        "confidence": str(e.confidence),
                    }
                    for e in normalized
                ]
        except Exception as exc:
            logger.error("LLM Gateway NER extraction failed: %s — falling back to spaCy.", exc)

        # spaCy / rules fallback (synchronous)
        entities = self._extract_with_spacy(text)
        return [
            {
                "value": e.value,
                "type": e.type,
                "canonical_name": e.canonical_name or e.value,
                "confidence": str(e.confidence),
            }
            for e in entities
        ]

    def extract_entities_sync(self, text: str) -> list[dict[str, str]]:
        """Synchronous fallback for use in non-async contexts. spaCy/rules only."""
        if not text or not text.strip():
            return []

        entities = self._extract_with_spacy(text)
        return [
            {
                "value": e.value,
                "type": e.type,
                "canonical_name": e.canonical_name or e.value,
                "confidence": str(e.confidence),
            }
            for e in entities
        ]


# ── Singleton ─────────────────────────────────────────────────────────────────
# The old ner_service is kept for backward compatibility.
# New code should use ner_service_v2.

ner_service_v2 = NERServiceV2()
