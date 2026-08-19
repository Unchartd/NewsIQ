"""How one logical LLM call became twelve against an exhausted quota.

Measured over 15h of production: 30,170 Gemini calls, 29,524 of them returning
RESOURCE_EXHAUSTED, against 199 Bedrock calls. contradiction_detection alone
accounted for 26,152.

Three independent multipliers, each pinned below:

1. MODEL_FALLBACKS listed three entries per Gemini model, all
   provider="gemini", and the gateway sent the manifest `model_name` rather
   than the route entry's own model. With a single Gemini key in the pool that
   was the same key, the same model, three times.

   Both halves are now fixed: generate_stage honours route_cfg["model"], and
   the Gemini chains end in Bedrock. Because chains are no longer homogeneous,
   abandoning the whole chain on a 429 would skip a genuinely different
   provider — the gateway now marks the specific route model exhausted and
   skips only routes whose model is already spent.

2. _handle_exception tested the auth branch before the rate-limit branch using
   bare substring matches. A quota payload containing "403" anywhere was
   classified AuthenticationError, which is not RateLimitError, so the model was
   never marked exhausted. 414 traces read "Gemini authentication failed: 429
   RESOURCE_EXHAUSTED".

3. Four stages declared Gemini-only fallback chains. Both Gemini models draw on
   the same free-tier allowance, so those stages had no reachable model once it
   was spent — while Bedrock sat idle answering 97.8% of the calls it did get.
"""

import pytest

from app.ai.errors import AuthenticationError, RateLimitError
from app.ai.prompts.repository import prompt_repository
from app.ai.providers.gemini import GeminiProvider

# ── 1. An exhausted model abandons its whole chain ───────────────────────────


def test_exhausted_routes_are_skipped_individually():
    """A spent model must be skipped without abandoning the rest of the chain.

    The chain now ends in Bedrock, so the old "break out of the chain on a
    429" would have thrown away the cross-provider escape.
    """
    import inspect

    from app.ai.gateway import AIGateway

    src = inspect.getsource(AIGateway.generate_stage)

    assert "if await is_exhausted(route_model):" in src, (
        "each route must be checked against model health before it is tried"
    )
    assert "mark_exhausted(route_model" in src, (
        "the model that actually rate-limited must be the one marked"
    )
    assert "model_exhausted" not in src, (
        "the whole-chain abandon is wrong now that chains span providers"
    )


def test_generate_stage_honours_the_route_model():
    """Sending the manifest model to another provider's route is what kept
    MODEL_FALLBACKS single-provider, and starved every agent-driven stage."""
    import inspect

    from app.ai.gateway import AIGateway

    src = inspect.getsource(AIGateway.generate_stage)
    assert 'route_model = route_cfg.get("model") or model_name' in src
    assert "model=model_name," not in src, (
        "requests must name the route's model, not the manifest's preference"
    )


def test_gemini_chains_have_a_cross_provider_escape():
    """Agent-driven stages route ONLY through this table.

    entity_disambiguation, feedback_agent, cluster_verification, contradiction,
    reflection and judge have no prompt manifest, so the manifest-level
    fallback_models never apply to them. With Gemini-only entries here they
    died outright when the free tier was spent: 348 RESOURCE_EXHAUSTED errors
    in one 20-minute production window.
    """
    from app.ai.config import MODEL_FALLBACKS

    for model in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite"):
        providers = {entry["provider"] for entry in MODEL_FALLBACKS[model]}
        assert providers - {"gemini"}, (
            f"{model} routes only to {providers}; every agent-driven stage "
            "would still die when Gemini is exhausted"
        )
        # The escape must be last, so Gemini is still preferred while healthy.
        assert MODEL_FALLBACKS[model][0]["provider"] == "gemini"
        assert MODEL_FALLBACKS[model][-1]["provider"] != "gemini"


# ── 2. A 429 is a rate limit, whatever else the payload contains ─────────────


@pytest.mark.parametrize(
    "message",
    [
        # The real shape: a quota payload whose limit values contain "403".
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded "
        "your current quota', 'details': [{'quotaValue': '14403'}]}}",
        "429 RESOURCE_EXHAUSTED. quota exceeded, see https://ai.google.dev/403",
        "Resource exhausted: free_tier_requests, limit 403 per day",
    ],
)
def test_quota_errors_are_never_classified_as_auth_failures(message):
    """AuthenticationError is not RateLimitError, so it bypasses the breaker."""
    provider = GeminiProvider()
    classified = provider._handle_exception(Exception(message))

    assert isinstance(classified, RateLimitError), (
        f"classified as {type(classified).__name__}; the model would never be "
        "marked exhausted and would be retried with full backoff"
    )


def test_genuine_auth_failures_are_still_auth_failures():
    """The reorder must not swallow real credential problems."""
    provider = GeminiProvider()
    for message in ("401 Unauthorized", "API key not valid. Please pass a valid API key."):
        assert isinstance(provider._handle_exception(Exception(message)), AuthenticationError)


# ── 3. Every stage must have a non-Gemini escape ─────────────────────────────


@pytest.mark.parametrize(
    "stage",
    [
        "contradiction_detection",
        "source_comparison",
        "summary_refinement",
        "summary_reflection",
        "summary_generation",
        "entity_extraction",
        "event_extraction",
        "cluster_verification",
        "entity_linking",
    ],
)
def test_every_stage_can_escape_an_exhausted_gemini_quota(stage):
    """Both Gemini models share one free-tier allowance.

    A chain of gemini → gemini has no escape once it is spent, which is how
    contradiction_detection made 26,152 calls for 486 successes.
    """
    cfg = prompt_repository.model_config(stage)
    chain = [cfg.model] + list(cfg.fallback_models)
    non_gemini = [m for m in chain if not m.startswith("gemini")]

    assert non_gemini, f"{stage} routes only to Gemini: {chain}"
