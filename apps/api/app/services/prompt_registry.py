"""Prompt Registry proxy — delegates to app.ai.prompts.registry.

Maintains backward-compatible API contracts to eliminate drift while avoiding code duplication.
"""

from __future__ import annotations

import logging

from app.ai.prompts.registry import PromptTemplate
from app.ai.prompts.registry import prompt_registry as yaml_registry

logger = logging.getLogger(__name__)


class PromptRegistry:
    """Central registry proxy for all pipeline prompt templates.

    Accesses YAML prompt templates from app/ai/prompts/ under the hood.
    """

    def get(self, stage: str, variant: str | None = None) -> PromptTemplate:
        """Retrieve the prompt template for a pipeline stage."""
        try:
            return yaml_registry.get(stage, variant)
        except KeyError:
            # For backward compatibility with any legacy calls mapping contradiction_detection
            if stage == "contradiction_detection":
                return yaml_registry.get("contradiction_analysis", variant)
            raise

    def version(self, stage: str, variant: str | None = None) -> str:
        """Return the current version string for a stage's prompt."""
        return self.get(stage, variant).version

    def list_stages(self) -> list[str]:
        """Return all registered stage names."""
        # Hardcoded list corresponding to the YAML files
        return [
            "event_extraction",
            "entity_extraction",
            "entity_linking",
            "cluster_verification",
            "contradiction_detection",
            "source_comparison",
            "summary_generation",
            "summary_reflection",
        ]

    def register(self, prompt: PromptTemplate) -> None:
        """Register or override a prompt template in the YAML registry cache."""
        yaml_registry._cache[f"{prompt.stage}:default"] = prompt
        logger.info(
            "Registered override prompt template: stage=%s version=%s",
            prompt.stage,
            prompt.version,
        )


# Singleton proxy
prompt_registry = PromptRegistry()
