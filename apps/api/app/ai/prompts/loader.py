"""
app/ai/prompts/loader.py

PromptLoader — scans app/ai/prompts/*.yaml once at startup and builds raw PromptManifests.

Called exclusively by PromptCompiler during startup initialization.
Never called again after PromptRepository is built.

YAML schema is fully documented in manifest.py.
"""

from __future__ import annotations

import logging
import os
import string
from pathlib import Path
from typing import Any

import yaml

from app.ai.prompts.manifest import ModelConfig, PromptManifest

logger = logging.getLogger(__name__)

# Default prompts directory relative to this file
_DEFAULT_PROMPTS_DIR = Path(__file__).parent


class PromptLoaderError(Exception):
    """Raised when a YAML file cannot be parsed into a valid PromptManifest."""


class PromptLoader:
    """
    Scans all *.yaml files in the prompts directory and builds raw PromptManifest objects.

    'Raw' means the signature field is empty — PromptCompiler fills it after validation.

    Usage:
        loader = PromptLoader()
        raw_manifests = loader.load_all()   # {stage: PromptManifest}
    """

    def __init__(self, prompts_dir: Path | str | None = None) -> None:
        self.prompts_dir = Path(prompts_dir) if prompts_dir else _DEFAULT_PROMPTS_DIR

    def load_all(self) -> dict[str, PromptManifest]:
        """
        Scan all *.yaml files in prompts_dir (excluding _ prefixed files).

        Returns:
            {stage: PromptManifest} mapping. All manifests have signature="" (set by compiler).

        Raises:
            PromptLoaderError: If any YAML file is malformed or missing required fields.
        """
        manifests: dict[str, PromptManifest] = {}
        errors: list[str] = []

        yaml_files = sorted(self.prompts_dir.glob("*.yaml"))
        if not yaml_files:
            raise PromptLoaderError(f"No *.yaml files found in {self.prompts_dir}")

        for path in yaml_files:
            if path.name.startswith("_"):
                continue
            try:
                manifest = self._parse(path)
                if manifest.stage in manifests:
                    errors.append(
                        f"Duplicate stage '{manifest.stage}' found in {path.name} "
                        f"(already loaded from another file)"
                    )
                else:
                    manifests[manifest.stage] = manifest
                    logger.debug("Loaded prompt manifest: %s from %s", manifest.prompt_uri, path.name)
            except (KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
                errors.append(f"{path.name}: {exc}")

        if errors:
            raise PromptLoaderError(
                f"PromptLoader failed with {len(errors)} error(s):\n"
                + "\n".join(f"  • {e}" for e in errors)
            )

        logger.info("PromptLoader: loaded %d prompt manifests from %s", len(manifests), self.prompts_dir)
        return manifests

    def _parse(self, path: Path) -> PromptManifest:
        """Parse a single YAML file into a raw (unsigned) PromptManifest."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return self._build_manifest(raw, path.name)

    def _build_manifest(self, data: dict[str, Any], filename: str) -> PromptManifest:
        """Map a parsed YAML dict to a PromptManifest. Raises KeyError on missing required fields."""
        stage = self._require(data, "stage", filename)
        system = self._require(data, "system", filename).strip()
        template = self._require(data, "template", filename).strip()

        # Extract {variable} names from template
        template_variables = frozenset(
            field_name
            for _, field_name, _, _ in string.Formatter().parse(template)
            if field_name is not None
        )

        # Routing
        routing_data = self._require(data, "routing", filename)
        routing = ModelConfig(
            model=self._require(routing_data, "preferred_model", f"{filename}.routing"),
            fallback_models=tuple(routing_data.get("fallback_models", [])),
            temperature=float(routing_data.get("temperature", 0.1)),
            max_tokens=int(routing_data.get("max_tokens", 2048)),
            timeout_seconds=float(routing_data.get("timeout_seconds", 30.0)),
        )

        # Cache
        cache_data = data.get("cache", {})
        cacheable = bool(cache_data.get("cacheable", False))
        cache_ttl = int(cache_data["cache_ttl_seconds"]) if cache_data.get("cache_ttl_seconds") else None
        cache_inputs = tuple(cache_data.get("cache_inputs", []))

        # Dependencies
        deps_data = data.get("dependencies", {})
        prompt_dependencies = tuple(deps_data.get("prompt_dependencies", []))

        # Lifecycle
        lifecycle_data = data.get("lifecycle", {})
        lifecycle_state = lifecycle_data.get("state", "draft")
        replay_policy = lifecycle_data.get("replay_policy", "replayable")

        # Lineage
        lineage_data = data.get("lineage", {})
        superseded_raw = lineage_data.get("superseded_by")
        superseded_by = tuple(superseded_raw) if isinstance(superseded_raw, list) else None

        # Ownership
        ownership_data = data.get("ownership", {})

        # Compatibility
        compat_data = data.get("compatibility", {})

        return PromptManifest(
            prompt_uri=self._require(data, "prompt_uri", filename),
            stage=stage,
            version=self._require(data, "version", filename),
            schema_version=data.get("schema_version", "v1"),
            response_version=data.get("response_version", "v1"),
            pipeline_version=compat_data.get("min_pipeline_version", ">=0"),
            system=system,
            template=template,
            template_variables=template_variables,
            response_model=data.get("response_model"),
            routing=routing,
            cacheable=cacheable,
            cache_ttl_seconds=cache_ttl,
            cache_inputs=cache_inputs,
            prompt_dependencies=prompt_dependencies,
            lifecycle_state=lifecycle_state,
            replay_policy=replay_policy,
            parent_uri=lineage_data.get("parent_uri"),
            derived_from=lineage_data.get("derived_from"),
            created_at=str(lineage_data.get("created_at", "")),
            deprecated_at=lineage_data.get("deprecated_at"),
            deprecated_reason=lineage_data.get("deprecated_reason"),
            superseded_by=superseded_by,
            owner=ownership_data.get("owner", "unknown"),
            team=ownership_data.get("team", "unknown"),
            created_by=ownership_data.get("created_by", "system"),
            last_reviewed=ownership_data.get("last_reviewed"),
            documentation=ownership_data.get("documentation"),
            min_pipeline_version=compat_data.get("min_pipeline_version", ">=0"),
            min_schema_version=compat_data.get("min_schema_version", ">=0"),
            min_gateway_version=compat_data.get("min_gateway_version", ">=0"),
            signature="",  # Set by PromptCompiler
        )

    @staticmethod
    def _require(data: dict[str, Any], key: str, context: str) -> Any:
        """Extract a required key, raising a clear error if missing."""
        value = data.get(key)
        if value is None:
            raise KeyError(f"Required field '{key}' missing in {context}")
        return value
