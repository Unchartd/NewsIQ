"""Rules Engine for Story Lifecycle Transitions."""
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.models.models import Story, StoryLifecycleState

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "lifecycle_rules.yaml"


@dataclass
class TransitionDecision:
    """Represents a decision made by the Rules Engine."""
    target_state: StoryLifecycleState
    reason: str
    should_transition: bool


class LifecycleRulesEngine:
    """Evaluates story signals to determine if a lifecycle state transition is warranted."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config = self._load_config(config_path)
        self.transitions_config = self.config.get("transitions", {})

    def _load_config(self, path: Path) -> dict[str, Any]:
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except Exception:
            # Fallback configuration if file missing/invalid
            return {
                "transitions": {
                    "developing": {"min_articles": 3},
                    "monitoring": {"min_confidence": 0.80, "inactivity_hours": 6, "min_sources": 3, "max_contradiction": 0.2},
                    "stable": {"min_confidence": 0.95, "inactivity_hours": 24, "min_sources": 5, "max_contradiction": 0.1},
                    "archived": {"inactivity_hours": 168, "no_recent_discovery_hours": 168}
                }
            }

    def evaluate(self, story: Story) -> TransitionDecision:
        """Evaluates a story and returns a decision on whether to transition its state."""
        current_state = story.lifecycle_state

        if current_state == StoryLifecycleState.ARCHIVED:
            # Cannot transition out of archived automatically
            return TransitionDecision(StoryLifecycleState.ARCHIVED, "Story is already archived.", False)

        now = datetime.now(UTC)

        # Calculate inactivity
        hours_since_update = 0.0
        if story.last_significant_update_at:
            # ensure offset-aware
            last_update = story.last_significant_update_at
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=UTC)
            hours_since_update = (now - last_update).total_seconds() / 3600.0

        hours_since_discovery = 0.0
        if story.last_discovery_at:
            last_discovery = story.last_discovery_at
            if last_discovery.tzinfo is None:
                last_discovery = last_discovery.replace(tzinfo=UTC)
            hours_since_discovery = (now - last_discovery).total_seconds() / 3600.0
        else:
            hours_since_discovery = float('inf')

        confidence = story.confidence_score or 0.0
        sources = story.source_diversity_count or 0
        contradiction = story.contradiction_score or 0.0
        # Number of articles isn't directly on the story model without loading the relationship,
        # but if we need it for 'developing', we could just use source_diversity_count as proxy,
        # or assume len(story.articles) if eagerly loaded.
        articles_count = len(story.articles) if hasattr(story, 'articles') and story.articles else sources

        # Evaluate emerging -> developing
        if current_state == StoryLifecycleState.EMERGING:
            conf = self.transitions_config.get("developing", {})
            min_articles = conf.get("min_articles", 3)
            if articles_count >= min_articles:
                return TransitionDecision(
                    target_state=StoryLifecycleState.DEVELOPING,
                    reason=f"Articles count ({articles_count}) met threshold ({min_articles})",
                    should_transition=True
                )

        # Evaluate developing -> monitoring
        if current_state == StoryLifecycleState.DEVELOPING:
            conf = self.transitions_config.get("monitoring", {})
            if (confidence >= conf.get("min_confidence", 0.80) and
                hours_since_update >= conf.get("inactivity_hours", 6) and
                sources >= conf.get("min_sources", 3) and
                contradiction <= conf.get("max_contradiction", 0.2)):
                return TransitionDecision(
                    target_state=StoryLifecycleState.MONITORING,
                    reason=f"Inactivity {hours_since_update:.1f}h, Conf {confidence:.2f}, Sources {sources}, Contradiction {contradiction:.2f}",
                    should_transition=True
                )

        # Evaluate monitoring -> stable
        if current_state == StoryLifecycleState.MONITORING:
            conf = self.transitions_config.get("stable", {})
            if (confidence >= conf.get("min_confidence", 0.95) and
                hours_since_update >= conf.get("inactivity_hours", 24) and
                sources >= conf.get("min_sources", 5) and
                contradiction <= conf.get("max_contradiction", 0.1)):
                return TransitionDecision(
                    target_state=StoryLifecycleState.STABLE,
                    reason=f"Inactivity {hours_since_update:.1f}h, Conf {confidence:.2f}, Sources {sources}, Contradiction {contradiction:.2f}",
                    should_transition=True
                )

        # Evaluate stable -> archived
        if current_state == StoryLifecycleState.STABLE:
            conf = self.transitions_config.get("archived", {})
            if (hours_since_update >= conf.get("inactivity_hours", 168) and
                hours_since_discovery >= conf.get("no_recent_discovery_hours", 168)):
                return TransitionDecision(
                    target_state=StoryLifecycleState.ARCHIVED,
                    reason=f"No updates for {hours_since_update:.1f}h, no discovery for {hours_since_discovery:.1f}h",
                    should_transition=True
                )

        # No transition needed
        try:
            target_enum = StoryLifecycleState(current_state)
        except ValueError:
            target_enum = StoryLifecycleState.EMERGING
        return TransitionDecision(target_enum, "No thresholds met.", False)
