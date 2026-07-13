"""
app/ai/prompts/compiler.py

PromptCompiler — validates all raw PromptManifests and computes their signatures.

Called once by PromptRepository during startup initialization.
Fails startup (raises RuntimeError) on any validation error.
Emits warnings for registered-but-unused prompts.

Validation checks:
  1. Template syntax — all {variables} are syntactically valid
  2. Dependency existence — all prompt_dependencies resolve to known stages or deterministic stages
  3. Cycle detection — topological DFS detects circular dependencies
  4. Lifecycle state — must be one of the valid lifecycle states
  5. Response model — declared response_model must exist as a Pydantic BaseModel
  6. Model routing — preferred_model must exist in MODEL_FALLBACKS config
  7. Cache inputs — all cache_inputs must be known fields
  8. Unused detection — production prompts with no runtime callers emit warnings
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import string
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from app.ai.prompts.manifest import PromptManifest

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

VALID_LIFECYCLE_STATES = frozenset({
    "draft", "testing", "replay", "approved", "production", "deprecated", "archived"
})

# Deterministic pipeline stages that can appear in prompt_dependencies
# without requiring a YAML prompt file.
DETERMINISTIC_STAGES = frozenset({
    "knowledge_graph",
    "timeline",
    "publisher",
    "synthesis_orchestrator",
    "feedback_agent",
    "embedding",
    "deduplication",
    "crawling",
})

# Production prompts that have verified runtime callers in services.
# Update this set when a new ai_gateway.generate(stage=...) call is added.
KNOWN_PROMPT_CALLERS: frozenset[str] = frozenset({
    "event_extraction",
    "entity_extraction",
    "entity_linking",
    "cluster_verification",
    "contradiction_detection",
    "source_comparison",
    "summary_generation",
    "summary_refinement",
    "summary_reflection",
})


# ── Compiler ───────────────────────────────────────────────────────────────────

class PromptCompiler:
    """
    Validates raw PromptManifests and produces signed, ready-to-use manifests.

    Usage:
        loader = PromptLoader()
        raw = loader.load_all()
        compiler = PromptCompiler()
        compiled = compiler.compile_all(raw)  # Raises RuntimeError on failure
    """

    def compile_all(self, raw: dict[str, PromptManifest]) -> dict[str, PromptManifest]:
        """
        Validate all manifests, detect cycles, sign each, and return the compiled registry.

        Raises:
            RuntimeError: If any validation error is found. Startup is aborted.
        """
        errors: list[str] = []

        # 1. Per-manifest validation
        for stage, manifest in raw.items():
            stage_errors = self._validate_manifest(manifest, raw)
            errors.extend(f"[{stage}] {e}" for e in stage_errors)

        # 2. Cross-manifest: cycle detection
        cycle_errors = self._detect_cycles(raw)
        errors.extend(cycle_errors)

        if errors:
            raise RuntimeError(
                f"\n\n🚨 PromptCompiler: startup aborted — {len(errors)} validation error(s):\n"
                + "\n".join(f"  • {e}" for e in errors)
                + "\n\nFix all YAML errors before starting the service.\n"
            )

        # 3. Sign all manifests
        compiled: dict[str, PromptManifest] = {
            stage: self._sign(manifest) for stage, manifest in raw.items()
        }

        # 4. Warn on unused production prompts (non-fatal)
        self._warn_unused(compiled)

        logger.info(
            "PromptCompiler: %d prompts compiled and signed successfully.",
            len(compiled),
        )
        return compiled

    # ── Per-manifest validation ────────────────────────────────────────────────

    def _validate_manifest(
        self, manifest: PromptManifest, all_manifests: dict[str, PromptManifest]
    ) -> list[str]:
        errors: list[str] = []
        errors.extend(self._validate_template_syntax(manifest))
        errors.extend(self._validate_dependencies(manifest, all_manifests))
        errors.extend(self._validate_lifecycle_state(manifest))
        errors.extend(self._validate_response_model(manifest))
        errors.extend(self._validate_model_routing(manifest))
        errors.extend(self._validate_cache_inputs(manifest))
        return errors

    def _validate_template_syntax(self, m: PromptManifest) -> list[str]:
        """Ensure all {placeholder} expressions in system + template are syntactically valid."""
        errors = []
        for field_name, content in (("system", m.system), ("template", m.template)):
            try:
                # Parse without substituting to find syntax errors
                list(string.Formatter().parse(content))
            except (ValueError, KeyError) as exc:
                errors.append(f"Invalid {field_name} template syntax: {exc}")
        return errors

    def _validate_dependencies(
        self, m: PromptManifest, all_manifests: dict[str, PromptManifest]
    ) -> list[str]:
        """All prompt_dependencies must exist as a registered stage or known deterministic stage."""
        errors = []
        for dep in m.prompt_dependencies:
            if dep not in all_manifests and dep not in DETERMINISTIC_STAGES:
                errors.append(
                    f"Dependency '{dep}' is not a registered prompt stage or deterministic stage. "
                    f"Known prompt stages: {sorted(all_manifests)}. "
                    f"Deterministic stages: {sorted(DETERMINISTIC_STAGES)}."
                )
        return errors

    def _validate_lifecycle_state(self, m: PromptManifest) -> list[str]:
        if m.lifecycle_state not in VALID_LIFECYCLE_STATES:
            return [
                f"lifecycle_state '{m.lifecycle_state}' is not valid. "
                f"Must be one of: {sorted(VALID_LIFECYCLE_STATES)}"
            ]
        return []

    def _validate_response_model(self, m: PromptManifest) -> list[str]:
        """Verify declared response_model exists in app.models.llm_responses as a Pydantic model."""
        if not m.response_model:
            return []
        try:
            import importlib
            from pydantic import BaseModel

            module = importlib.import_module("app.models.llm_responses")
            cls = getattr(module, m.response_model, None)
            if cls is None:
                return [
                    f"response_model '{m.response_model}' not found in app.models.llm_responses. "
                    f"Available classes: {[c for c in dir(module) if not c.startswith('_')]}"
                ]
            if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
                return [f"response_model '{m.response_model}' must be a Pydantic BaseModel subclass."]
        except ImportError as exc:
            return [f"Could not import app.models.llm_responses for response_model validation: {exc}"]
        return []

    def _validate_model_routing(self, m: PromptManifest) -> list[str]:
        """Verify preferred_model exists in the gateway MODEL_FALLBACKS configuration."""
        try:
            from app.ai.config import MODEL_FALLBACKS

            if m.routing.model not in MODEL_FALLBACKS and m.routing.model != "mock":
                return [
                    f"preferred_model '{m.routing.model}' not found in app.ai.config.MODEL_FALLBACKS. "
                    f"Available models: {sorted(MODEL_FALLBACKS)}"
                ]
        except ImportError:
            logger.warning("Could not import MODEL_FALLBACKS for routing validation (non-fatal).")
        return []

    def _validate_cache_inputs(self, m: PromptManifest) -> list[str]:
        """For cacheable prompts, verify cache_inputs are plausible (template vars or known meta-fields)."""
        if not m.cacheable:
            return []
        # Meta-fields that are valid cache inputs even if not in the template
        meta_fields = frozenset({"story_input_hash", "version", "stage", "article_id", "story_id"})
        errors = []
        for ci in m.cache_inputs:
            if ci not in m.template_variables and ci not in meta_fields:
                errors.append(
                    f"cache_input '{ci}' not found in template variables {set(m.template_variables)} "
                    f"or known meta-fields {meta_fields}."
                )
        return errors

    # ── Cross-manifest: cycle detection ───────────────────────────────────────

    def _detect_cycles(self, manifests: dict[str, PromptManifest]) -> list[str]:
        """
        Topological DFS to detect circular dependency chains.

        Returns a list of error strings describing each cycle found.
        """
        errors: list[str] = []
        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(stage: str, path: list[str]) -> None:
            if stage in in_stack:
                # Found a cycle — reconstruct the cycle path
                cycle_start = path.index(stage)
                cycle_path = " → ".join(path[cycle_start:] + [stage])
                errors.append(f"Dependency cycle detected: {cycle_path}")
                return
            if stage in visited or stage not in manifests:
                return

            visited.add(stage)
            in_stack.add(stage)

            for dep in manifests[stage].prompt_dependencies:
                if dep in manifests:  # Only follow prompt stage deps (not deterministic)
                    dfs(dep, path + [stage])

            in_stack.discard(stage)

        for stage in manifests:
            if stage not in visited:
                dfs(stage, [])

        return errors

    # ── Signature ─────────────────────────────────────────────────────────────

    def _sign(self, m: PromptManifest) -> PromptManifest:
        """
        Compute a deterministic SHA256 signature over all content-affecting fields.

        Fields included:
          system | template | schema_version | response_version | version |
          temperature | preferred_model | sorted(fallbacks) |
          sorted(dependencies) | sorted(cache_inputs) | lifecycle_state

        Changing ANY of these fields produces a new signature, which:
          - Triggers a new DB seed version
          - Invalidates the stage-level cache key
          - Appears in admin audit trails
        """
        sig_parts = [
            m.system,
            m.template,
            m.schema_version,
            m.response_version,
            m.version,
            str(m.routing.temperature),
            m.routing.model,
            ",".join(sorted(m.routing.fallback_models)),
            ",".join(sorted(m.prompt_dependencies)),
            ",".join(sorted(m.cache_inputs)),
            m.lifecycle_state,
        ]
        signature = hashlib.sha256("|".join(sig_parts).encode("utf-8")).hexdigest()
        return dataclasses.replace(m, signature=signature)

    # ── Unused prompt warnings ─────────────────────────────────────────────────

    def _warn_unused(self, compiled: dict[str, PromptManifest]) -> None:
        """
        Emit warnings for production prompts that have no known runtime callers.

        Only production prompts are checked — draft/testing prompts are expected
        to have no callers during development.

        To silence a warning: either add a gateway.generate(stage=<stage>) call site
        or change lifecycle_state to 'testing' / 'deprecated'.
        """
        for stage, manifest in compiled.items():
            if manifest.lifecycle_state != "production":
                continue
            if stage not in KNOWN_PROMPT_CALLERS:
                logger.warning(
                    "⚠️  Prompt '%s' (%s) is lifecycle=production but has no entry "
                    "in KNOWN_PROMPT_CALLERS. If this prompt has no runtime callers, "
                    "set lifecycle_state: deprecated or testing. "
                    "If it does have callers, add '%s' to KNOWN_PROMPT_CALLERS in compiler.py.",
                    manifest.prompt_uri,
                    stage,
                    stage,
                )
