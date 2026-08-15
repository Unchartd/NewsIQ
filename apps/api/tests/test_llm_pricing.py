"""Cost must be computed once, from one table, and never silently zeroed.

cost_usd was 0.00 on 17,333 of 17,333 llm_traces rows — every LLM call ever
made — so the cost dashboard read zero throughout. Two causes, both here:

1. Two pricing tables. app/ai/gateway.py held the live models; app/core/trace.py
   held only gemini-2.x, which this deployment has never run.
2. The gateway computed the correct cost from the provider's usage numbers, and
   track_llm_call's `finally` block recomputed it from the stale table and threw
   the right answer away.

The silent `.get(model, {"input": 0.0, "output": 0.0})` default is what let it
go unnoticed: an unpriced model was indistinguishable from a free one.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.ai import pricing
from app.ai.gateway import PRICING_TABLE as GATEWAY_TABLE
from app.core.trace import LLM_PRICING as TRACE_TABLE
from app.core.trace import PipelineRun, StageSpan, track_llm_call


def test_there_is_exactly_one_pricing_table():
    """The two modules must reference the same object, not two copies."""
    assert GATEWAY_TABLE is pricing.PRICING_TABLE
    assert TRACE_TABLE is pricing.PRICING_TABLE


@pytest.mark.parametrize("model", ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"])
def test_models_actually_running_in_production_are_priced(model):
    """These two account for 18,347 of the 17,333+ recorded calls."""
    assert pricing.is_priced(model), f"{model} runs in production but has no rate"
    assert pricing.calculate_llm_cost(model, 1_000_000, 0) > 0


def test_unknown_model_reports_unknown_not_free():
    """A zero is indistinguishable from a free call and reads as authoritative."""
    assert pricing.calculate_llm_cost("no-such-model-xyz", 1_000_000, 1_000_000) is None


def test_bedrock_models_are_declared_rather_than_guessed():
    """Live on Bedrock, rate unconfirmed — listed so they are not silently zeroed."""
    for model in ("qwen.qwen3-vl-235b-a22b-instruct", "deepseek.v3.2"):
        assert model in pricing.UNPRICED_MODELS
        assert not pricing.is_priced(model), (
            "if a real rate has been confirmed, move it into PRICING_TABLE "
            "and drop it from UNPRICED_MODELS"
        )


def test_legacy_models_still_price_for_historical_traces():
    assert pricing.calculate_llm_cost("gemini-2.5-flash", 1_000_000, 1_000_000) == 0.15 + 0.60


@pytest.mark.asyncio
async def test_tracker_does_not_overwrite_a_cost_the_caller_computed():
    """The gateway prices from provider usage; the tracer must not discard it."""
    with (
        patch("app.core.trace._persist_llm_call", AsyncMock()),
        patch("app.core.trace.langfuse_client"),
    ):
        run = PipelineRun(trigger="manual", pipeline_type="batch")
        async with run:
            async with StageSpan(run, stage="summary"):
                async with track_llm_call(
                    provider="bedrock",
                    model="qwen.qwen3-vl-235b-a22b-instruct",
                    stage="summary",
                    system_prompt="s",
                    user_prompt="u",
                ) as call:
                    call.input_tokens = 1000
                    call.output_tokens = 500
                    # What the gateway does after reading provider usage.
                    call.cost_usd = 0.004242

    assert call.cost_usd == 0.004242, (
        "the tracer recomputed and discarded the gateway's cost — this is what "
        "left every trace at 0.00"
    )


@pytest.mark.asyncio
async def test_tracker_still_prices_when_the_caller_did_not():
    with (
        patch("app.core.trace._persist_llm_call", AsyncMock()),
        patch("app.core.trace.langfuse_client"),
    ):
        run = PipelineRun(trigger="manual", pipeline_type="batch")
        async with run:
            async with StageSpan(run, stage="summary"):
                async with track_llm_call(
                    provider="gemini",
                    model="gemini-3.5-flash-lite",
                    stage="summary",
                    system_prompt="s",
                    user_prompt="u",
                ) as call:
                    call.input_tokens = 1_000_000
                    call.output_tokens = 0

    assert call.cost_usd == pytest.approx(0.075)
