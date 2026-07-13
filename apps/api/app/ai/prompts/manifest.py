"""
app/ai/prompts/manifest.py

PromptManifest — the authoritative compiled definition of a versioned LLM prompt.

Loaded from YAML by PromptLoader. Validated and signed by PromptCompiler.
Stored immutably in PromptRepository after startup.

Design principles:
  - Immutable (frozen dataclass)
  - Self-contained (carries model routing, cache policy, dependencies)
  - Auditable (carries ownership, lineage, lifecycle)
  - Typed (all fields explicit, no Any)
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclasses.dataclass(frozen=True)
class ModelConfig:
    """Routing config for a single prompt stage. Replaces CAPABILITY_ROUTING lookups."""

    model: str
    fallback_models: tuple[str, ...]
    temperature: float
    max_tokens: int
    timeout_seconds: float


@dataclasses.dataclass(frozen=True)
class PromptManifest:
    """
    Compiled, immutable definition of a versioned LLM prompt.

    Every field is populated at startup from YAML by PromptLoader + PromptCompiler.
    The PromptRepository holds these after startup; no code instantiates them directly.

    URI format: newsiq://prompt/<stage>
    Example:    newsiq://prompt/summary_generation
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    prompt_uri: str
    """Immutable semantic URI. e.g. 'newsiq://prompt/summary_generation'"""

    stage: str
    """Runtime lookup key. e.g. 'summary_generation'. Must match YAML filename stem."""

    version: str
    """Prompt content version. e.g. 'v2.0.0'. Increment when system/template changes."""

    schema_version: str
    """Response schema version. e.g. 'v1'. Increment when Pydantic model changes."""

    response_version: str
    """Expected JSON response format version. Independent of schema_version."""

    pipeline_version: str
    """Minimum pipeline version this prompt requires. e.g. '>=1.4'"""

    # ── Content ───────────────────────────────────────────────────────────────
    system: str
    """System prompt text (role/rules)."""

    template: str
    """User prompt template with {variable} placeholders."""

    template_variables: frozenset[str]
    """Variables extracted from template at compile time. e.g. frozenset({'title', 'content'})"""

    response_model: str | None
    """
    Pydantic class name for structured output validation.
    e.g. 'StorySummaryResponse'. None = unstructured text output.
    Must exist in app.models.llm_responses.
    """

    # ── Model Routing (replaces CAPABILITY_ROUTING) ───────────────────────────
    routing: ModelConfig
    """Preferred model, fallbacks, temperature, tokens, timeout. Source of truth for gateway."""

    # ── Cache Policy ──────────────────────────────────────────────────────────
    cacheable: bool
    """Whether responses for this prompt can be cached."""

    cache_ttl_seconds: int | None
    """Cache TTL. None = no-cache (for non-cacheable prompts)."""

    cache_inputs: tuple[str, ...]
    """Fields that compose the cache key. e.g. ('story_input_hash', 'version')"""

    # ── Dependency Graph ──────────────────────────────────────────────────────
    prompt_dependencies: tuple[str, ...]
    """
    Stages this prompt depends on. Used for:
    - Replay ordering (topological sort)
    - Startup validation (dependency existence + cycle detection)
    - Admin DAG visualization

    Can include both PromptStages ('contradiction_detection') and
    deterministic stages ('knowledge_graph', 'timeline').
    """

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    lifecycle_state: str
    """
    One of: draft | testing | replay | approved | production | deprecated | archived.
    Only 'production' prompts are included in KNOWN_PROMPT_CALLERS validation.
    """

    replay_policy: str
    """'replayable' | 'no-replay'. Non-cacheable correction prompts should be no-replay."""

    # ── Lineage ───────────────────────────────────────────────────────────────
    parent_uri: str | None
    """URI of the prompt this was derived from. None = original."""

    derived_from: str | None
    """Version string of the parent prompt this derives from."""

    created_at: str
    """ISO date string. e.g. '2026-07-14'"""

    deprecated_at: str | None
    """ISO date when this prompt was deprecated. None = still active."""

    deprecated_reason: str | None
    """Human-readable reason for deprecation. e.g. 'Replaced by Pipeline C multi-stage synthesis'"""

    superseded_by: tuple[str, ...] | None
    """
    URIs or stage names this prompt was replaced by.
    e.g. ('summary_generation', 'knowledge_graph', 'source_comparison')
    Displayed in Admin Prompt Viewer for deprecated prompts.
    """

    # ── Ownership ─────────────────────────────────────────────────────────────
    owner: str
    """Team/module owner. e.g. 'synthesis'"""

    team: str
    """Engineering team. e.g. 'ai'"""

    created_by: str
    """Author. e.g. 'system' or 'engineer-handle'"""

    last_reviewed: str | None
    """ISO date of last review. None = never reviewed."""

    documentation: str | None
    """Relative path to documentation. e.g. 'docs/prompts/summary_generation.md'"""

    # ── Compatibility Matrix ──────────────────────────────────────────────────
    min_pipeline_version: str
    """Minimum NewsIQ pipeline version required. e.g. '>=1.4'"""

    min_schema_version: str
    """Minimum DB schema version required. e.g. '>=1'"""

    min_gateway_version: str
    """Minimum AI Gateway version required. e.g. '>=2'"""

    # ── Computed at compile time ──────────────────────────────────────────────
    signature: str
    """
    SHA256 over all content-affecting fields:
    system | template | schema_version | response_version | version |
    temperature | preferred_model | sorted(fallbacks) |
    sorted(dependencies) | sorted(cache_inputs) | lifecycle_state

    Changing ANY of these fields produces a new signature, triggering
    a new DB seed version and invalidating caches.
    """

    def render_messages(self, **variables: str) -> list[dict[str, str]]:
        """Render system + user messages with template variables filled in."""
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.template.format(**variables)},
        ]

    def is_active(self) -> bool:
        """True if this prompt is in an active (non-deprecated/archived) state."""
        return self.lifecycle_state in ("draft", "testing", "replay", "approved", "production")

    def is_production(self) -> bool:
        """True if this prompt is in the production lifecycle state."""
        return self.lifecycle_state == "production"

    def is_cacheable(self) -> bool:
        """True if responses for this prompt should be cached."""
        return self.cacheable and self.cache_ttl_seconds is not None

    @property
    def short_uri(self) -> str:
        """Return the stage portion of the URI. e.g. 'summary_generation'"""
        return self.stage

    def __repr__(self) -> str:
        return (
            f"PromptManifest("
            f"uri={self.prompt_uri!r}, "
            f"version={self.version!r}, "
            f"lifecycle={self.lifecycle_state!r}, "
            f"model={self.routing.model!r}"
            f")"
        )
