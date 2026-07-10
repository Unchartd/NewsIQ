"""Event Validation Service (Phase B4 Dual-Stage)."""

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

# Try to load spaCy for fast entity extraction
try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        nlp = None
        logging.warning("spaCy installed but en_core_web_sm not found. Falling back to simple NER.")
except ImportError:
    nlp = None

try:
    from app.core.metrics import (
        newsiq_event_validation_decisions_total,
        newsiq_event_validation_latency_seconds,
        newsiq_event_validation_savings_total,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "event_validation.yaml"
logger = logging.getLogger(__name__)


class ValidationOutcome(StrEnum):
    PASS = "PASS"
    MAYBE = "MAYBE"
    FAIL = "FAIL"


@dataclass
class DecisionLog:
    outcome: ValidationOutcome
    stage: str
    score: float
    details: dict[str, Any]
    reason: str


@dataclass
class StoryAnchor:
    """Represents the centroid and metadata of an existing Story."""
    story_id: str
    headline: str
    first_seen_at: datetime
    last_updated_at: datetime
    primary_entities: set[str]
    top_locations: set[str]
    category: str | None
    event_type: str | None
    centroid_vector: list[float] | None = None
    entity_graph_ids: set[str] = None


class EventValidationService:
    """Service to handle deterministic Stage A and Qdrant-based Stage B event validation."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config = self._load_config(config_path)
        self.stage_a_weights = self.config.get("stage_a", {}).get("weights", {})
        self.stage_a_thresh = self.config.get("stage_a", {}).get("thresholds", {})
        self.stage_b_thresh = self.config.get("stage_b", {}).get("thresholds", {})

    def _load_config(self, path: Path) -> dict[str, Any]:
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning("Failed to load %s: %s. Using default config.", path, e)
            return {
                "stage_a": {
                    "weights": {
                        "entity_overlap": 35,
                        "location": 20,
                        "time_proximity": 15,
                        "title_similarity": 20,
                        "publisher_trust": 10
                    },
                    "thresholds": {"pass": 60, "maybe": 45}
                },
                "stage_b": {
                    "thresholds": {"cosine": 0.72, "entity_overlap": 2}
                }
            }

    def _extract_entities(self, text: str) -> set[str]:
        """Extract lightweight entities deterministically."""
        if not text:
            return set()
        if nlp:
            doc = nlp(text)
            return {ent.text.lower() for ent in doc.ents if ent.label_ in ("PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT")}
        # Fallback to crude capitalization-based extraction if spacy model not loaded
        words = text.split()
        return {w.lower() for w in words if w.istitle() and len(w) > 3}

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        set1 = set(s1.lower().split())
        set2 = set(s2.lower().split())
        if not set1 or not set2:
            return 0.0
        return len(set1.intersection(set2)) / len(set1.union(set2))

    def _cosine_similarity(self, v1: list[float], v2: list[float]) -> float:
        if not v1 or not v2:
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def validate_stage_a(self, article: Any, anchor: StoryAnchor) -> DecisionLog:
        """
        Stage A - Pre-Embedding validation.
        Zero API calls. Fully deterministic. Fast.
        """
        start_time = datetime.now()
        details = {}
        score = 0.0

        # 1. Entity Overlap (Max weight)
        article_title_entities = self._extract_entities(article.title)
        shared_entities = article_title_entities.intersection(anchor.primary_entities)

        # If anchor has no primary entities yet, we score proportionally or give partial credit
        ent_weight = self.stage_a_weights.get("entity_overlap", 35)
        if anchor.primary_entities:
            ent_score = (len(shared_entities) / min(len(article_title_entities) or 1, len(anchor.primary_entities))) * ent_weight
        else:
            ent_score = ent_weight * 0.5  # Neutral if anchor is empty
        score += ent_score
        details["entity_overlap_score"] = ent_score
        details["shared_entities"] = list(shared_entities)

        # 2. Location Overlap
        # (Assuming location is parsed in entities for article)
        loc_weight = self.stage_a_weights.get("location", 20)
        shared_locs = article_title_entities.intersection(anchor.top_locations)
        if anchor.top_locations:
            loc_score = (len(shared_locs) / min(len(article_title_entities) or 1, len(anchor.top_locations))) * loc_weight
        else:
            loc_score = loc_weight * 0.5
        score += loc_score
        details["location_score"] = loc_score

        # 3. Time Proximity
        time_weight = self.stage_a_weights.get("time_proximity", 15)
        article_time = article.published_at or datetime.now(UTC).replace(tzinfo=None)
        anchor_time = anchor.first_seen_at

        # Naive timezone handling if required
        if article_time.tzinfo is not None:
            article_time = article_time.replace(tzinfo=None)
        if anchor_time.tzinfo is not None:
            anchor_time = anchor_time.replace(tzinfo=None)

        hours_diff = abs((article_time - anchor_time).total_seconds()) / 3600.0
        if hours_diff <= 24:
            time_score = time_weight
        elif hours_diff <= 72:
            time_score = time_weight * 0.5
        else:
            time_score = 0
        score += time_score
        details["time_proximity_score"] = time_score
        details["hours_diff"] = hours_diff

        # 4. Title Similarity (Jaccard)
        title_weight = self.stage_a_weights.get("title_similarity", 20)
        jaccard = self._jaccard_similarity(article.title, anchor.headline)
        title_score = jaccard * title_weight
        score += title_score
        details["title_similarity_score"] = title_score

        # 5. Publisher Trust
        trust_weight = self.stage_a_weights.get("publisher_trust", 10)
        # Assuming source tier logic (1 is best, 5 is worst)
        tier = getattr(article.source, "trust_tier", 5) if hasattr(article, "source") else 5
        if tier <= 3:
            trust_score = trust_weight
        elif tier == 4:
            trust_score = trust_weight * 0.5
        else:
            trust_score = 0
        score += trust_score
        details["publisher_trust_score"] = trust_score
        details["tier"] = tier
        trust_score = max(0.0, 100.0 - ((tier - 1) * 20.0))

        # Weighted Score
        w = self.stage_a_weights
        final_score = (
            ent_score +
            loc_score +
            time_score +
            title_score +
            (trust_score * (w.get("publisher_trust", 10) / 100.0))
        )

        details = {
            "entity_overlap_score": ent_score,
            "location_overlap_score": loc_score,
            "time_proximity_score": time_score,
            "title_similarity_score": title_score,
            "publisher_trust_score": trust_score,
            "tier": tier
        }

        pass_thresh = self.stage_a_thresh.get("pass", 60)
        maybe_thresh = self.stage_a_thresh.get("maybe", 45)

        if final_score >= pass_thresh:
            outcome = ValidationOutcome.PASS
            reason = f"High score ({final_score:.1f} >= {pass_thresh})."
        elif final_score >= maybe_thresh:
            outcome = ValidationOutcome.MAYBE
            reason = f"Borderline score ({final_score:.1f} between {maybe_thresh} and {pass_thresh})."
        else:
            outcome = ValidationOutcome.FAIL
            reason = f"Low score ({final_score:.1f} < {maybe_thresh})."

        latency = (datetime.now() - start_time).total_seconds()

        if METRICS_AVAILABLE:
            try:
                newsiq_event_validation_latency_seconds.labels(stage="stage_a").observe(latency)
                newsiq_event_validation_decisions_total.labels(stage="stage_a", outcome=outcome.value).inc()
                if outcome == ValidationOutcome.FAIL:
                    newsiq_event_validation_savings_total.labels(resource="llm_calls").inc()
                    newsiq_event_validation_savings_total.labels(resource="embeddings").inc()
            except Exception as e:
                logger.warning("Failed to record Stage A metrics: %s", e)

        return DecisionLog(
            outcome=outcome,
            stage="Stage A (Pre-Embedding)",
            score=final_score,
            details=details,
            reason=reason
        )

    def validate_stage_b(self, article: Any, anchor: StoryAnchor, article_vector: list[float], article_canonical_entity_ids: set[str]) -> DecisionLog:
        """
        Stage B - Post-Embedding validation.
        Requires vector lookup and entity graph intersection.
        """
        start_time = datetime.now()
        details = {}

        cosine_thresh = self.stage_b_thresh.get("cosine", 0.72)
        entity_thresh = self.stage_b_thresh.get("entity_overlap", 2)

        cosine = 0.0
        if anchor.centroid_vector and article_vector:
            cosine = self._cosine_similarity(article_vector, anchor.centroid_vector)
        details["cosine_similarity"] = cosine

        anchor_entities = anchor.entity_graph_ids or set()
        shared_entities = len(article_canonical_entity_ids.intersection(anchor_entities))
        details["shared_canonical_entities"] = shared_entities

        if cosine >= cosine_thresh or shared_entities >= entity_thresh:
            outcome = ValidationOutcome.PASS
            reason = "Met vector similarity or entity graph threshold."
        elif cosine >= cosine_thresh - 0.05 or shared_entities >= max(1, entity_thresh - 1):
            outcome = ValidationOutcome.MAYBE
            reason = "Borderline vector/entity similarity. Requires reflection."
        else:
            outcome = ValidationOutcome.FAIL
            reason = f"Cosine ({cosine:.2f}) and entity overlap ({shared_entities}) too low."

        latency = (datetime.now() - start_time).total_seconds()
        if METRICS_AVAILABLE:
            try:
                newsiq_event_validation_latency_seconds.labels(stage="stage_b").observe(latency)
                newsiq_event_validation_decisions_total.labels(stage="stage_b", outcome=outcome.value).inc()
                if outcome == ValidationOutcome.FAIL:
                    newsiq_event_validation_savings_total.labels(resource="llm_calls").inc()
            except Exception as e:
                logger.warning("Failed to record Stage B metrics: %s", e)

        # Stage B doesn't use a weighted score in the same way, we can pass cosine as a proxy score
        return DecisionLog(
            outcome=outcome,
            stage="Stage B (Post-Embedding)",
            score=cosine,
            details=details,
            reason=reason
        )

event_validation_service = EventValidationService()
