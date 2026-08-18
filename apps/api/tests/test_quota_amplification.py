"""How one logical LLM call became twelve against an exhausted quota.

Measured over 15h of production: 30,170 Gemini calls, 29,524 of them returning
RESOURCE_EXHAUSTED, against 199 Bedrock calls. contradiction_detection alone
accounted for 26,152.

Three independent multipliers, each pinned below:

1. MODEL_FALLBACKS lists three entries per Gemini model, all provider="gemini",
   and the gateway sends the manifest `model_name` rather than the route entry's
   own model. With a single Gemini key in the pool that is the same key, the
   same model, three times. `break` on RateLimitError left the attempt loop but
   not the chain, so an exhausted model burned all three.

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


def test_rate_limited_model_breaks_out_of_its_chain():
    """The `break` must leave the chain loop, not just the attempt loop."""
    import inspect

    from app.ai.gateway import AIGateway

    src = inspect.getsource(AIGateway.generate_stage)

    assert "model_exhausted = True" in src, "the rate-limit handler must flag the model"
    assert "if model_exhausted:" in src, "the chain loop must honour the flag"


def test_gemini_chain_entries_are_not_distinct_routes():
    """Documents *why* abandoning the chain loses nothing.

    If these entries ever become genuinely distinct providers, this test fails
    and the break-out above needs revisiting.
    """
    from app.ai.config import MODEL_FALLBACKS

    for model in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite"):
        providers = {entry["provider"] for entry in MODEL_FALLBACKS[model]}
        assert providers == {"gemini"}, (
            f"{model} now routes to {providers}; abandoning the chain on a 429 "
            "would skip a genuinely different provider"
        )


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
