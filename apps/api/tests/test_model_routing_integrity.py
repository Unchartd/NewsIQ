"""Regression tests: every configured model must route to a provider that serves it.

Production spent days POSTing Bedrock model names to Google's API. The prompt
manifests named `qwen.qwen3-vl-235b-a22b-instruct` and
`deepseek-ai/deepseek-v4-flash` as fallback models, but generate_stage()
resolves manifest names through MODEL_FALLBACKS — and neither was registered
there. The unknown-model branch defaulted to provider="gemini", so both
fallback tiers of every prompt-driven stage returned:

    Gemini provider error: 404 Not Found

The Bedrock tier added for cross-provider redundancy therefore never ran once,
and the pipeline had no redundancy at all exactly when Gemini was
rate-limited. `deepseek-ai/deepseek-v4-flash` does not exist on any configured
provider — it was a phantom name that could only ever 404.

These tests close the loop between the three places a model can be named:
prompt manifests, MODEL_FALLBACKS, and CAPABILITY_ROUTING.
"""

import pathlib

import pytest
import yaml

from app.ai.config import CAPABILITY_ROUTING, MODEL_FALLBACKS

PROMPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "ai" / "prompts"


def _manifest_models() -> dict[str, list[str]]:
    """Every model named by any prompt manifest -> the manifests naming it."""
    found: dict[str, list[str]] = {}

    def walk(node, stem):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "preferred_model" and isinstance(value, str):
                    found.setdefault(value, []).append(stem)
                elif key == "fallback_models" and isinstance(value, list):
                    for m in value:
                        if isinstance(m, str):
                            found.setdefault(m, []).append(stem)
                else:
                    walk(value, stem)
        elif isinstance(node, list):
            for item in node:
                walk(item, stem)

    for path in PROMPTS_DIR.glob("*.yaml"):
        try:
            walk(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, path.stem)
        except yaml.YAMLError:
            continue
    return found


def test_every_manifest_model_is_registered_for_routing():
    """A manifest name absent from MODEL_FALLBACKS cannot be routed correctly."""
    unregistered = {
        model: sorted(set(files))
        for model, files in _manifest_models().items()
        if model not in MODEL_FALLBACKS
    }
    assert not unregistered, (
        "prompt manifests name models missing from MODEL_FALLBACKS: "
        f"{unregistered}. generate_stage() resolves manifest names through "
        "MODEL_FALLBACKS, so these cannot reach their real provider."
    )


def test_every_capability_route_model_is_registered():
    """CAPABILITY_ROUTING and MODEL_FALLBACKS must agree on what exists."""
    missing = set()
    for capability, route in CAPABILITY_ROUTING.items():
        for tier in ("primary", "fallback", "lastFallback"):
            model = route[tier]["model"]
            if model != "mock" and model not in MODEL_FALLBACKS:
                missing.add((capability, tier, model))
    assert not missing, f"capability routes name unregistered models: {sorted(missing)}"


def test_registered_models_route_to_their_own_provider():
    """A model must never be registered against a provider that cannot serve it.

    Guards the specific shape of the incident: a Bedrock model routed to Gemini.
    """
    prefix_owner = {
        "gemini-": "gemini",
        "qwen.": "bedrock",
        "deepseek.": "bedrock",
    }
    wrong = []
    for model, routes in MODEL_FALLBACKS.items():
        for prefix, expected in prefix_owner.items():
            if model.startswith(prefix):
                for cfg in routes:
                    if cfg["provider"] != expected:
                        wrong.append((model, cfg["provider"], expected))
    assert not wrong, f"models routed to the wrong provider: {wrong}"


def test_unknown_model_returns_no_route_instead_of_guessing_gemini():
    """Refusing to guess is what turns a silent 404 into a visible error.

    The mock gate short-circuits routing inside a test run, so it is disabled
    here to exercise the real production lookup.
    """
    import importlib
    from unittest.mock import patch

    # The package re-exports the singleton under the module's own name, so
    # resolve the real module explicitly before patching its bound import.
    cr_mod = importlib.import_module("app.ai.router.capability_router")

    with patch.object(cr_mod, "in_test_run", return_value=False):
        assert cr_mod.capability_router.get_model_route("definitely-not-a-real-model-xyz") == []


@pytest.mark.parametrize("phantom", ["deepseek-ai/deepseek-v4-flash"])
def test_phantom_models_are_gone_from_manifests(phantom):
    """This name existed on no provider; it could only ever 404."""
    assert phantom not in _manifest_models()
