"""OpenRouter as the cross-provider escape when Gemini fails.

Production had no working fallback: Gemini's free tier was spent or answering
503 "high demand", and the Bedrock key was rejected, so every AI stage failed.
The OpenRouter key worked, but the provider could not serve structured output:
it asked for "valid JSON matching the schema" without sending the schema —
the bug that made 1,351 of 1,352 Bedrock responses fail validation.

Chosen from a live comparison on the real event-extraction prompt:
DeepSeek V4 Flash with reasoning off (5.8s, the only correct event type) and
Mercury 2.5 with reasoning low (3.3-3.9s). With default reasoning the same
models took 38-111s, so the reasoning setting is part of each route.
"""

import json
from collections import defaultdict
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from app.ai.config import MODEL_FALLBACKS
from app.ai.interfaces import GatewayRequest, GatewayResponse
from app.ai.providers.openrouter import OpenRouterProvider
from app.core.llm_pricing import PRICING_TABLE

DEEPSEEK = "deepseek/deepseek-v4-flash-0731"
MERCURY = "inception/mercury-2.5"


class _Answer(BaseModel):
    verdict: str = Field(description="publish or hold")
    confidence: float


def _request(**overrides) -> GatewayRequest:
    values = {"model": DEEPSEEK, "messages": [{"role": "user", "content": "decide"}]} | overrides
    return GatewayRequest(**values)


# ── Provider request shape ───────────────────────────────────────────────────


def test_the_schema_is_sent_both_as_format_and_as_instruction():
    params = OpenRouterProvider()._prepare_params(_request(response_format=_Answer))

    fmt = params["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["name"] == "_Answer"
    assert set(fmt["json_schema"]["schema"]["properties"]) == {"verdict", "confidence"}

    instruction = params["messages"][-1]
    assert instruction["role"] == "system"
    assert '"verdict"' in instruction["content"], (
        "hosts that only promise JSON need the field names in the prompt"
    )


def test_a_plain_dict_format_falls_back_to_json_mode():
    params = OpenRouterProvider()._prepare_params(_request(response_format={"type": "object"}))
    assert params["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("reasoning", [{"enabled": False}, {"effort": "low"}])
def test_the_route_reasoning_setting_reaches_openrouter(reasoning):
    params = OpenRouterProvider()._prepare_params(
        _request(response_format=_Answer, reasoning=reasoning)
    )
    extra = params["extra_body"]
    assert extra["reasoning"] == reasoning
    assert extra["provider"] == {"require_parameters": True}, (
        "a host that ignores the reasoning setting turns a 6s call into 100s"
    )
    assert extra["usage"] == {"include": True}


def test_no_reasoning_setting_is_sent_when_the_route_has_none():
    params = OpenRouterProvider()._prepare_params(_request())
    assert "reasoning" not in params["extra_body"]
    assert "provider" not in params["extra_body"]
    assert "response_format" not in params


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (SimpleNamespace(cost=0.00047), 0.00047),
        (SimpleNamespace(model_extra={"cost": "0.00039"}), 0.00039),
        (SimpleNamespace(), 0.0),
        (None, 0.0),
    ],
)
def test_the_billed_cost_is_read_from_the_response(usage, expected):
    assert OpenRouterProvider._billed_cost(SimpleNamespace(usage=usage)) == pytest.approx(expected)


# ── Routing ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("chain", ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"])
def test_gemini_chains_try_openrouter_before_bedrock(chain):
    routes = MODEL_FALLBACKS[chain]
    providers = [r["provider"] for r in routes]
    assert providers[:2] == ["gemini", "gemini"], "Gemini stays first"
    assert providers.index("openrouter") < providers.index("bedrock")

    openrouter = {r["model"]: r.get("reasoning") for r in routes if r["provider"] == "openrouter"}
    assert openrouter == {DEEPSEEK: {"enabled": False}, MERCURY: {"effort": "low"}}
    assert [r["model"] for r in routes if r["provider"] == "openrouter"] == [DEEPSEEK, MERCURY]


def test_every_openrouter_chat_route_has_a_fallback_price():
    chat_models = {
        r["model"]
        for routes in MODEL_FALLBACKS.values()
        for r in routes
        if r["provider"] == "openrouter" and "embedding" not in r["model"]
    }
    assert chat_models >= {DEEPSEEK, MERCURY}
    missing = sorted(m for m in chat_models if m not in PRICING_TABLE)
    assert not missing, f"unpriced OpenRouter chat models: {missing}"


# ── Gateway behaviour ────────────────────────────────────────────────────────


@asynccontextmanager
async def _no_llm_trace(**_kwargs):
    yield SimpleNamespace()


async def _run_extraction_through(route: dict, billed_cost: float):
    """Run the real generate_stage with one route, returning (request, record)."""
    from app.ai import gateway as gw

    answer = json.dumps({"primary_event": {"event_type": "LEGAL"}})
    client = MagicMock()
    client.generate = AsyncMock(
        return_value=GatewayResponse(
            content=answer,
            input_tokens=1000,
            output_tokens=1000,
            total_tokens=2000,
            cost_usd=billed_cost,
            provider=route["provider"],
            model=route["model"],
        )
    )
    persist = AsyncMock()
    with (
        patch.object(gw, "filter_healthy", AsyncMock(side_effect=lambda models: models[:1])),
        patch.object(gw, "is_exhausted", AsyncMock(return_value=False)),
        patch.object(gw, "track_llm_call", _no_llm_trace),
        patch.object(gw.capability_router, "get_model_route", return_value=[(client, "k", route)]),
        patch.object(gw.capability_router, "health_trackers", defaultdict(MagicMock)),
        patch.object(gw.ai_gateway, "_persist_execution_record", persist),
        patch.object(gw.ai_cache, "get", AsyncMock(return_value=None)),
        patch.object(gw.ai_cache, "set", AsyncMock()),
    ):
        await gw.ai_gateway.generate_stage(
            stage="event_extraction",
            prompt_variables={
                "title": "t",
                "source_name": "s",
                "published_at": "unknown",
                "content": "c",
            },
        )
    return client.generate.await_args.args[0], persist.await_args.kwargs


async def test_generate_stage_sends_the_route_reasoning():
    route = MODEL_FALLBACKS[DEEPSEEK][0]
    request, _ = await _run_extraction_through(route, billed_cost=0.0)
    assert request.model == DEEPSEEK
    assert request.reasoning == {"enabled": False}


async def test_a_fallback_call_is_priced_as_the_model_that_served_it():
    """It used to be priced by the chain's name — i.e. as Gemini."""
    route = MODEL_FALLBACKS[DEEPSEEK][0]
    _, record = await _run_extraction_through(route, billed_cost=0.0)
    listed = PRICING_TABLE[DEEPSEEK]
    assert record["model"] == DEEPSEEK
    assert record["cost"] == pytest.approx((listed["input"] + listed["output"]) / 1000)


async def test_a_billed_cost_reported_by_the_provider_wins():
    route = MODEL_FALLBACKS[DEEPSEEK][0]
    _, record = await _run_extraction_through(route, billed_cost=0.00047)
    assert record["cost"] == pytest.approx(0.00047)


# ── Total deadline ───────────────────────────────────────────────────────────


async def test_a_call_that_never_finishes_hits_the_route_deadline():
    """OpenRouter trickles bytes to keep a slow request alive, so the SDK's
    per-read timeout never fires. Measured after the v1.49.0 rollout: two
    extraction calls sent 8 and 10 minutes earlier were still open, receiving
    a few bytes every ~2.4s, against a 45s route timeout."""
    import asyncio
    import time

    from app.ai.errors import TimeoutError as GatewayTimeoutError
    from app.ai.interfaces import APIKey
    from app.ai.providers import openrouter as provider_module

    async def trickling_forever(**_kwargs):
        await asyncio.sleep(3600)

    fake_client = MagicMock()
    fake_client.chat.completions.create = trickling_forever
    with patch.object(provider_module, "AsyncOpenAI", return_value=fake_client) as sdk:
        started = time.perf_counter()
        with pytest.raises(GatewayTimeoutError):
            # The outer guard only stops a regression from hanging the suite;
            # it raises asyncio's TimeoutError, which this does not accept.
            await asyncio.wait_for(
                OpenRouterProvider().generate(
                    _request(response_format=_Answer, timeout=0.2),
                    APIKey(key="k", provider="openrouter"),
                ),
                timeout=5,
            )
        elapsed = time.perf_counter() - started

    assert elapsed < 2, f"the call ran {elapsed:.1f}s past a 0.2s deadline"
    assert sdk.call_args.kwargs["max_retries"] == 0, (
        "the gateway retries each route; SDK retries only multiply a failing route's time"
    )
