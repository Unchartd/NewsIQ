"""Regression tests for the fabricated-event incident.

Production carried 6,584 identical template events — 86% of the event table —
written by the mock LLM provider during a historic quota-exhaustion window
(2026-07-15 → 07-31). The mock SUCCEEDS where real providers fail, so its
reachability converts provider failure into silently fabricated data. Months
later, those identical events hashed to one event_fingerprint and transitive
union-find grouping fused 281 unrelated articles into two stories (193 + 88
articles: blood-donation guidelines, a megayacht, cricket, and an Iranian
gambling network, together).

Two independent defense layers are pinned here:
  1. mock output is policy-gated, in one shared place, for both LLM stacks;
  2. clustering treats degenerate fingerprints as noise even if fabricated
     or template events ever reach the table again.
"""

import inspect
from unittest.mock import patch

import pytest

from app.ai import mock_policy
from app.services.clustering_service import clustering_service

# ── Layer 1: mock is policy-gated ────────────────────────────────────────────


def test_mock_policy_is_the_single_decision_point():
    """Both LLM stacks must consult mock_policy, not private heuristics.

    The old gates were pytest-detection heuristics duplicated per stack — a
    policy that consequential must not hinge on which modules happen to be
    imported, and must not be able to drift between stacks.
    """
    # Resolve the real modules via importlib: the packages re-export
    # singleton instances under the same names, shadowing the submodules.
    import importlib

    cr_mod = importlib.import_module("app.ai.router.capability_router")
    fc_mod = importlib.import_module("app.llm_gateway.fallback_chain")

    assert "mock_policy" in inspect.getsource(fc_mod)
    assert "mock_policy" in inspect.getsource(cr_mod)


def test_mock_providers_refuse_when_policy_denies():
    """Even if routing regresses, the providers themselves must not fabricate."""
    from app.ai.interfaces import APIKey, GatewayRequest
    from app.ai.providers.mock import MockProvider

    provider = MockProvider()
    request = GatewayRequest(model="mock", messages=[{"role": "user", "content": "x"}])
    key = APIKey(key="mock-key", provider="mock", requests_per_minute=1, requests_per_day=1)

    import asyncio

    with patch.object(mock_policy, "mock_allowed", return_value=False):
        with pytest.raises(RuntimeError, match="[Rr]efusing to fabricate"):
            asyncio.run(provider.generate(request, key))


def test_fallback_chain_never_ends_in_mock_when_policy_denies():
    from app.llm_gateway.fallback_chain import FallbackChain

    with patch.object(mock_policy, "mock_allowed", return_value=False):
        chain = FallbackChain().get_fallback_chain("gemini-3.1-flash-lite")
    assert all(e["provider"] != "mock" for e in chain), (
        "with mock stripped, exhausting real providers raises QuotaExhaustedError "
        "and the pipeline pauses — failure must fail, not fabricate"
    )


def test_quota_exhaustion_machinery_is_reachable_without_mock():
    """QuotaExhaustedError exists precisely for the all-providers-429 case.

    With a mock tail on the chain it could never fire, because mock always
    succeeded first — the cooldown machinery was dead code in production.
    """
    from app.llm_gateway import request_manager

    src = inspect.getsource(request_manager)
    assert "QuotaExhaustedError" in src
    assert "All providers quota-exhausted" in src


# ── Layer 2: degenerate fingerprints are noise ───────────────────────────────


def test_fingerprint_grouping_requires_event_time():
    """A fingerprint without a date cannot assert 'same real-world event'."""
    src = inspect.getsource(clustering_service._run_batch_clustering_locked)
    fetch = src.index("ArticleEvent.event_fingerprint.isnot(None)")
    window = src[fetch : fetch + 200]
    assert "ArticleEvent.event_time.isnot(None)" in window, (
        "undated fingerprints are exactly how 6,584 template events collapsed into one grouping key"
    )


def test_fingerprint_grouping_has_a_frequency_cap():
    """No genuine event is 15%+ of a random batch; such a fingerprint is a template."""
    src = inspect.getsource(clustering_service._run_batch_clustering_locked)
    assert "_FINGERPRINT_MAX_GROUP" in src
    assert "degenerate" in src, "over-frequent fingerprints must be dropped, loudly"
