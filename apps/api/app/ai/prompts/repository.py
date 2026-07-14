"""
app/ai/prompts/repository.py

PromptRepository — the immutable prompt platform API.

Built once at application startup from compiled PromptManifests.
Zero filesystem I/O after initialization.

All consumers use the singleton `prompt_repository`:
    from app.ai.prompts.repository import prompt_repository

    manifest = prompt_repository.get("summary_generation")
    messages = prompt_repository.messages("summary_generation", knowledge_graph=kg_str)
    cfg = prompt_repository.model_config("summary_generation")
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, Any

from app.ai.prompts.manifest import ModelConfig, PromptManifest

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PromptRepositoryError(KeyError):
    """Raised when a stage or URI cannot be resolved."""


class PromptRepository:
    """
    Immutable, in-memory store of all compiled PromptManifests.

    Built once at startup by the startup hook in app/main.py:
        loader → compiler → repository

    After initialization:
    - Zero filesystem reads
    - Thread-safe (immutable state)
    - Hot-swappable for replay/A-B testing via replace()

    12-method platform API:
        get, get_by_uri, resolve,           ← retrieval
        messages, model_config,             ← rendering
        dependencies, reverse_dependencies, topological_order,  ← graph
        production, testing, replay, list_stages,              ← lifecycle filters
        validate, export_manifest, export_graph,               ← inspection
        replace                                                ← hot-swap
    """

    def __init__(self, manifests: dict[str, PromptManifest]) -> None:
        self._by_stage: dict[str, PromptManifest] = dict(manifests)
        self._by_uri: dict[str, PromptManifest] = {m.prompt_uri: m for m in manifests.values()}
        # Pre-compute reverse dependency map
        self._reverse_deps: dict[str, list[str]] = self._build_reverse_deps(manifests)
        # Pre-compute topological order
        self._topo_order: list[str] = self._compute_topological_order(manifests)

    # ── Core Retrieval ─────────────────────────────────────────────────────────

    def get(self, stage: str) -> PromptManifest:
        """
        Get the active manifest for a stage (any lifecycle state).

        Raises:
            PromptRepositoryError: If stage is not registered.
        """
        try:
            return self._by_stage[stage]
        except KeyError:
            raise PromptRepositoryError(
                f"No prompt registered for stage '{stage}'. "
                f"Available stages: {sorted(self._by_stage)}"
            ) from None

    def get_by_uri(self, uri: str) -> PromptManifest:
        """
        Get manifest by stable semantic URI.

        Example:
            prompt_repository.get_by_uri("newsiq://prompt/summary_generation")
        """
        try:
            return self._by_uri[uri]
        except KeyError:
            raise PromptRepositoryError(
                f"No prompt registered for URI '{uri}'. Available URIs: {sorted(self._by_uri)}"
            ) from None

    def resolve(self, stage: str, lifecycle: str = "production") -> PromptManifest:
        """
        Get manifest for a specific lifecycle state.

        Used by:
        - Production traffic: resolve("summary_generation", "production")
        - Replay: resolve("summary_generation", "replay")
        - A/B testing: resolve("summary_generation", "testing")

        Raises:
            PromptRepositoryError: If no manifest with that stage + lifecycle is found.
        """
        manifest = self.get(stage)
        if manifest.lifecycle_state == lifecycle:
            return manifest
        raise PromptRepositoryError(
            f"Prompt '{stage}' exists but has lifecycle_state='{manifest.lifecycle_state}', "
            f"not '{lifecycle}'. "
            f"Check the YAML lifecycle.state field or use get('{stage}') for any lifecycle."
        )

    # ── Rendering ─────────────────────────────────────────────────────────────

    def messages(self, stage: str, **variables: Any) -> list[dict[str, str]]:
        """
        Render OpenAI-style system + user message list for a stage.

        Args:
            stage: Prompt stage name. e.g. 'summary_generation'
            **variables: Template variable values. Must match template's {placeholders}.

        Returns:
            [{"role": "system", "content": ...}, {"role": "user", "content": ...}]

        Raises:
            KeyError: If a required template variable is missing.
        """
        manifest = self.get(stage)
        return manifest.render_messages(**variables)

    def model_config(self, stage: str) -> ModelConfig:
        """
        Return the model routing config for a stage.

        The gateway uses this to resolve preferred_model + fallback_models.
        No other code should know which model a stage uses.
        """
        return self.get(stage).routing

    # ── Dependency Graph ───────────────────────────────────────────────────────

    def dependencies(self, stage: str) -> list[str]:
        """
        Return the direct dependencies of a stage.

        Example:
            prompt_repository.dependencies("summary_generation")
            → ["knowledge_graph", "contradiction_detection", "source_comparison", "timeline"]
        """
        return list(self.get(stage).prompt_dependencies)

    def reverse_dependencies(self, stage: str) -> list[str]:
        """
        Return all stages that directly depend on this stage.

        Useful for impact analysis: "if I change contradiction_detection, what breaks?"

        Example:
            prompt_repository.reverse_dependencies("contradiction_detection")
            → ["source_comparison", "summary_generation"]
        """
        return self._reverse_deps.get(stage, [])

    def topological_order(self) -> list[str]:
        """
        Return all prompt stages in dependency-first topological order.

        Used by replay orchestration to determine execution order automatically.
        Deterministic stage dependencies (knowledge_graph, timeline) are excluded
        from the returned list since they have no YAML manifests.

        Example:
            → ["event_extraction", "entity_extraction", "entity_linking",
               "cluster_verification", "contradiction_detection", "source_comparison",
               "summary_generation", "summary_refinement", "summary_reflection"]
        """
        return list(self._topo_order)

    # ── Lifecycle Filters ──────────────────────────────────────────────────────

    def production(self) -> list[PromptManifest]:
        """All manifests in production lifecycle state."""
        return [m for m in self._by_stage.values() if m.lifecycle_state == "production"]

    def testing(self) -> list[PromptManifest]:
        """All manifests in testing lifecycle state."""
        return [m for m in self._by_stage.values() if m.lifecycle_state == "testing"]

    def replay(self) -> list[PromptManifest]:
        """All manifests in replay lifecycle state."""
        return [m for m in self._by_stage.values() if m.lifecycle_state == "replay"]

    def list_stages(self) -> list[str]:
        """All registered stage names, sorted alphabetically."""
        return sorted(self._by_stage)

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        """
        Runtime health check. Returns list of issues. Empty list = healthy.

        Called by /health and admin endpoints.
        """
        issues: list[str] = []
        for stage, manifest in self._by_stage.items():
            if not manifest.signature:
                issues.append(f"[{stage}] Missing signature — manifest was not compiled.")
            if manifest.lifecycle_state not in (
                "draft",
                "testing",
                "replay",
                "approved",
                "production",
                "deprecated",
                "archived",
            ):
                issues.append(f"[{stage}] Invalid lifecycle_state: {manifest.lifecycle_state!r}")
        return issues

    # ── Export (Admin API) ────────────────────────────────────────────────────

    def export_manifest(self) -> list[dict[str, Any]]:
        """
        Serialize all manifests for the admin /admin/prompts/export endpoint.

        Returns a list of dicts — one per registered prompt.
        """
        result = []
        for m in sorted(self._by_stage.values(), key=lambda m: m.stage):
            result.append(
                {
                    "prompt_uri": m.prompt_uri,
                    "stage": m.stage,
                    "version": m.version,
                    "schema_version": m.schema_version,
                    "lifecycle_state": m.lifecycle_state,
                    "preferred_model": m.routing.model,
                    "fallback_models": list(m.routing.fallback_models),
                    "cacheable": m.cacheable,
                    "cache_ttl_seconds": m.cache_ttl_seconds,
                    "prompt_dependencies": list(m.prompt_dependencies),
                    "replay_policy": m.replay_policy,
                    "owner": m.owner,
                    "team": m.team,
                    "last_reviewed": m.last_reviewed,
                    "documentation": m.documentation,
                    "signature": m.signature[:16] + "...",  # Truncated for display
                    "parent_uri": m.parent_uri,
                    "deprecated_at": m.deprecated_at,
                    "deprecated_reason": m.deprecated_reason,
                    "superseded_by": list(m.superseded_by) if m.superseded_by else None,
                }
            )
        return result

    def export_graph(self) -> dict[str, Any]:
        """
        Export the dependency graph as nodes + edges for DAG visualization.

        Format compatible with React Flow / dagre / D3.

        Returns:
            {
                "nodes": [{"id": stage, "label": stage, "lifecycle": ..., "model": ...}],
                "edges": [{"source": dep, "target": stage}]
            }
        """
        nodes = []
        edges = []

        for stage, m in self._by_stage.items():
            nodes.append(
                {
                    "id": stage,
                    "label": stage.replace("_", " ").title(),
                    "prompt_uri": m.prompt_uri,
                    "lifecycle": m.lifecycle_state,
                    "model": m.routing.model,
                    "cacheable": m.cacheable,
                    "is_production": m.is_production(),
                }
            )
            for dep in m.prompt_dependencies:
                edges.append({"source": dep, "target": stage, "type": "dependency"})

        return {"nodes": nodes, "edges": edges}

    # ── Hot Swap (Replay / Admin) ──────────────────────────────────────────────

    def replace(self, new_manifests: dict[str, PromptManifest]) -> PromptRepository:
        """
        Create a NEW repository from a different set of manifests.

        Does NOT mutate self. Production traffic always uses the original singleton.
        Replay jobs hold a local reference to the returned repository.

        Usage:
            replay_repo = prompt_repository.replace(replay_manifests)
            result_a = await run_pipeline(repo=prompt_repository)
            result_b = await run_pipeline(repo=replay_repo)
        """
        return PromptRepository(new_manifests)

    # ── Private graph helpers ──────────────────────────────────────────────────

    @staticmethod
    def _build_reverse_deps(manifests: dict[str, PromptManifest]) -> dict[str, list[str]]:
        """Build reverse dependency map: {stage → [stages that depend on it]}."""
        reverse: dict[str, list[str]] = {s: [] for s in manifests}
        for stage, m in manifests.items():
            for dep in m.prompt_dependencies:
                if dep in reverse:
                    reverse[dep].append(stage)
        return reverse

    @staticmethod
    def _compute_topological_order(manifests: dict[str, PromptManifest]) -> list[str]:
        """
        Kahn's algorithm for topological sort (BFS-based, stable ordering).

        Only includes stages with YAML manifests (skips deterministic stages in dependencies).
        Returns stages in dependency-first order for replay orchestration.
        """
        # Build in-degree count (only for prompt stages, not deterministic)
        in_degree: dict[str, int] = {s: 0 for s in manifests}
        adj: dict[str, list[str]] = {s: [] for s in manifests}

        for stage, m in manifests.items():
            for dep in m.prompt_dependencies:
                if dep in manifests:  # Only count prompt stage deps
                    in_degree[stage] += 1
                    adj[dep].append(stage)

        # BFS from zero-in-degree nodes
        queue: deque[str] = deque(s for s, deg in sorted(in_degree.items()) if deg == 0)
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in sorted(adj.get(node, [])):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If we couldn't process all nodes, there's a cycle (compiler should have caught it)
        if len(order) != len(manifests):
            logger.error(
                "Topological sort incomplete — possible cycle not caught by compiler. "
                "Processed %d of %d stages.",
                len(order),
                len(manifests),
            )

        return order

    def __repr__(self) -> str:
        counts = {
            "production": len(self.production()),
            "testing": len(self.testing()),
            "total": len(self._by_stage),
        }
        return f"PromptRepository(stages={counts['total']}, production={counts['production']}, testing={counts['testing']})"


# ── Singleton ──────────────────────────────────────────────────────────────────
# Initialized by the startup hook in app/main.py or dynamically on first access.
# Import this in services: from app.ai.prompts.repository import prompt_repository

prompt_repository: PromptRepository
_prompt_repository: PromptRepository | None = None


def _lazy_initialize() -> PromptRepository:
    logger.info("Initializing PromptRepository lazily...")
    from app.ai.prompts.compiler import PromptCompiler
    from app.ai.prompts.loader import PromptLoader

    loader = PromptLoader()
    raw = loader.load_all()

    compiler = PromptCompiler()
    compiled = compiler.compile_all(raw)
    return PromptRepository(compiled)


def __getattr__(name: str) -> Any:
    if name == "prompt_repository":
        global _prompt_repository
        if _prompt_repository is None:
            _prompt_repository = _lazy_initialize()
        return _prompt_repository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
