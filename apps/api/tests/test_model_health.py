"""Per-model circuit breaking for quota-exhausted LLMs.

Measured over twenty minutes with both Gemini models past their free-tier daily
limit: 540 Gemini attempts against 5 Bedrock, every Gemini call returning
RESOURCE_EXHAUSTED. The gateway retried each exhausted model three times with
exponential backoff, then moved to another exhausted Gemini model, before ever
reaching the Bedrock fallbacks the manifest declares.
"""

import inspect

import pytest

from app.ai import model_health


def test_daily_quota_gets_a_long_cooldown():
    """A spent daily allowance cannot recover in seconds."""
    err = (
        "Quota exceeded for metric: generativelanguage.googleapis.com/"
        "generate_content_free_tier_requests, limit: 500 ... 'status': 'RESOURCE_EXHAUSTED'"
    )
    assert model_health.cooldown_for(err) >= 3600


def test_transient_rate_limit_gets_a_short_cooldown():
    assert model_health.cooldown_for("429 Too Many Requests") < 3600


def test_provider_supplied_retry_delay_is_honoured():
    """Prefer the provider's own advice over our default when it is longer."""
    assert model_health.cooldown_for("Please retry in 300.5s.") >= 300


@pytest.mark.asyncio
async def test_exhausted_models_are_skipped(monkeypatch):
    async def fake_is_exhausted(model: str) -> bool:
        return model.startswith("gemini")

    monkeypatch.setattr(model_health, "is_exhausted", fake_is_exhausted)

    healthy = await model_health.filter_healthy(
        ["gemini-3.5-flash-lite", "qwen.qwen3-vl-235b-a22b-instruct", "deepseek.v3.2"]
    )
    assert healthy == ["qwen.qwen3-vl-235b-a22b-instruct", "deepseek.v3.2"]


@pytest.mark.asyncio
async def test_all_exhausted_still_attempts_rather_than_failing(monkeypatch):
    """An empty chain turns a slow call into a failed one — a long shot beats none."""

    async def fake_is_exhausted(model: str) -> bool:
        return True

    monkeypatch.setattr(model_health, "is_exhausted", fake_is_exhausted)

    models = ["a", "b"]
    assert await model_health.filter_healthy(models) == models


def test_gateway_skips_exhausted_models_and_stops_retrying_them():
    """The retry loop must abandon a rate-limited model instead of sleeping on it."""
    from app.ai.gateway import AIGateway

    src = inspect.getsource(AIGateway.generate_stage)

    assert "filter_healthy" in src, "the chain must exclude models known to be out of quota"
    assert "mark_exhausted" in src, "a rate-limited model must be recorded"

    rate_limit_idx = src.index("if isinstance(err, RateLimitError):")
    following = src[rate_limit_idx : rate_limit_idx + 300]
    assert "break" in following, (
        "a spent quota does not refill during backoff — the model must be abandoned, "
        "not retried three times"
    )
