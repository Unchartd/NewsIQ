import logging
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptTemplate:
    """A versioned prompt template with separated system/user content."""

    stage: str
    version: str
    system: str
    template: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def model(self) -> str:
        """Return the default/primary model mapped to this capability stage."""
        from app.ai.config import CAPABILITY_ROUTING
        route = CAPABILITY_ROUTING.get(self.stage)
        if route and "primary" in route:
            return route["primary"]["model"]
        return "gemini-2.5-flash"

    def system_message(self) -> dict[str, str]:
        """Return the system message dict for LLM API calls."""
        return {"role": "system", "content": self.system}

    def user_message(self, **kwargs: Any) -> dict[str, str]:
        """Return the user message dict with placeholders filled."""
        try:
            content = self.template.format(**kwargs)
        except KeyError as e:
            logger.error("Missing prompt template variable for %s: %s", self.stage, e)
            raise
        return {"role": "user", "content": content}

    def messages(self, **kwargs: Any) -> list[dict[str, str]]:
        """Return the full [system, user] message list."""
        return [self.system_message(), self.user_message(**kwargs)]


class PromptRegistry:
    """Central registry for loading and caching versioned prompt templates from YAML files."""

    def __init__(self, prompts_dir: str | None = None) -> None:
        if prompts_dir is None:
            prompts_dir = os.path.dirname(os.path.abspath(__file__))
        self.prompts_dir = prompts_dir
        self._cache: dict[str, PromptTemplate] = {}

    def get(self, stage: str, variant: str | None = None) -> PromptTemplate:
        """Retrieve a prompt template, supporting A/B testing variants.

        If variant is provided (e.g. 'B'), we look for {stage}_{variant}.yaml.
        Otherwise we fall back to {stage}.yaml.
        """
        cache_key = f"{stage}:{variant or 'default'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Determine filename
        filename = f"{stage}.yaml"
        if variant:
            variant_filename = f"{stage}_{variant}.yaml"
            variant_path = os.path.join(self.prompts_dir, variant_filename)
            if os.path.exists(variant_path):
                filename = variant_filename

        filepath = os.path.join(self.prompts_dir, filename)
        if not os.path.exists(filepath):
            raise KeyError(f"No prompt file found at: {filepath} for stage: {stage}")

        try:
            with open(filepath, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            prompt = PromptTemplate(
                stage=data["stage"],
                version=data["version"],
                system=data["system"].strip(),
                template=data["template"].strip(),
                metadata=data.get("metadata", {}),
            )
            self._cache[cache_key] = prompt
            return prompt
        except Exception as e:
            logger.error("Failed to load prompt template %s: %s", filepath, e)
            raise

    def version(self, stage: str, variant: str | None = None) -> str:
        """Return the version string for a stage's prompt."""
        return self.get(stage, variant).version

    def clear_cache(self) -> None:
        """Clear loaded prompt template cache."""
        self._cache.clear()


# Singleton
prompt_registry = PromptRegistry()
