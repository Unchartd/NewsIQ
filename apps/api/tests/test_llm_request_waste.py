"""LLM requests that were paid for and thrown away.

Measured on production for one day (2026-09-27, UTC): OpenRouter received
2,619 chat requests for 7 published stories.

- 190 replies were valid JSON followed by DeepSeek's end-of-sequence token,
  rejected as unparseable and retried.
- 445 calls hit the 30s deadline — billed anyway — and were retried on the same
  model, where more than half of second attempts failed again.
- 638 were EntityDisambiguationAgent calls: a second LLM call per entity, made
  because the Wikidata lookup searched with a descriptive query that
  wbsearchentities can never match. The agent then invented the QID — 10 of
  the 11 it stored that day named something else or did not exist.
- None of the agent calls were in ai_execution_records.
"""

import json
from collections import defaultdict
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.ai.errors import AuthenticationError
from app.ai.errors import TimeoutError as GatewayTimeoutError
from app.ai.interfaces import APIKey, GatewayRequest, GatewayResponse
from app.ai.json_payload import extract_json_text
from app.ai.providers import openrouter as provider_module
from app.ai.providers.openrouter import OpenRouterProvider
from app.services.entity_linker import EntityResolution, entity_linker

DEEPSEEK = "deepseek/deepseek-v4-flash-0731"
LEAKED_EOS = "<｜end▁of▁sentence｜>"
EVENT_ANSWER = json.dumps({"primary_event": {"event_type": "LEGAL"}})


class _Answer(BaseModel):
    verdict: str
    confidence: float


# ── Extracting the JSON object ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        # The production case, verbatim shape.
        ('{"canonical_name": "M25 motorway"}' + LEAKED_EOS, '{"canonical_name": "M25 motorway"}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('Here is the answer: {"a": {"b": "}"}}', '{"a": {"b": "}"}}'),
        ('  {"a": 1}  ', '{"a": 1}'),
    ],
)
def test_the_first_json_object_is_taken_from_the_reply(reply, expected):
    assert extract_json_text(reply) == expected
    json.loads(extract_json_text(reply))


@pytest.mark.parametrize("reply", ["", "   ", "no json here", '{"a": '])
def test_a_reply_without_an_object_still_fails_to_parse(reply):
    """Empty or truncated replies are real failures and must still be retried."""
    with pytest.raises(json.JSONDecodeError):
        json.loads(extract_json_text(reply))


async def test_openrouter_accepts_a_reply_with_a_leaked_end_token():
    reply = '{"verdict": "publish", "confidence": 0.9}' + LEAKED_EOS
    sdk_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, cost=0.0001),
        provider="SomeHost",
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=sdk_response)

    with patch.object(provider_module, "AsyncOpenAI", return_value=fake_client):
        response = await OpenRouterProvider().generate(
            GatewayRequest(
                model=DEEPSEEK,
                messages=[{"role": "user", "content": "decide"}],
                response_format=_Answer,
            ),
            APIKey(key="k", provider="openrouter"),
        )

    assert response.parsed == _Answer(verdict="publish", confidence=0.9)
    assert response.content == '{"verdict": "publish", "confidence": 0.9}'


def test_the_host_that_served_a_call_is_read_from_the_response():
    assert OpenRouterProvider._served_by(SimpleNamespace(provider="DeepInfra")) == "DeepInfra"
    assert (
        OpenRouterProvider._served_by(SimpleNamespace(model_extra={"provider": "Chutes"}))
        == "Chutes"
    )
    assert OpenRouterProvider._served_by(SimpleNamespace()) == "unknown"


def test_ignored_hosts_are_sent_alongside_require_parameters(monkeypatch):
    monkeypatch.setattr(provider_module.settings, "OPENROUTER_IGNORED_PROVIDERS", ["BadHost"])
    params = OpenRouterProvider()._prepare_params(
        GatewayRequest(
            model=DEEPSEEK,
            messages=[{"role": "user", "content": "decide"}],
            response_format=_Answer,
        )
    )
    assert params["extra_body"]["provider"] == {
        "require_parameters": True,
        "ignore": ["BadHost"],
    }


def test_no_host_is_ignored_by_default(monkeypatch):
    monkeypatch.setattr(provider_module.settings, "OPENROUTER_IGNORED_PROVIDERS", [])
    params = OpenRouterProvider()._prepare_params(
        GatewayRequest(model=DEEPSEEK, messages=[{"role": "user", "content": "hi"}])
    )
    assert "provider" not in params["extra_body"]


# ── Gateway retry policy ─────────────────────────────────────────────────────


@asynccontextmanager
async def _no_llm_trace(**_kwargs):
    yield SimpleNamespace()


def _answering_client(content: str = EVENT_ANSWER) -> MagicMock:
    client = MagicMock()
    client.generate = AsyncMock(
        return_value=GatewayResponse(
            content=content,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_usd=0.0001,
            provider="openrouter",
            model=DEEPSEEK,
        )
    )
    return client


def _failing_client(error: Exception) -> MagicMock:
    client = MagicMock()
    client.generate = AsyncMock(side_effect=error)
    return client


def _gateway_patches(gw, chain, persist):
    return (
        patch.object(gw, "filter_healthy", AsyncMock(side_effect=lambda models: models[:1])),
        patch.object(gw, "is_exhausted", AsyncMock(return_value=False)),
        patch.object(gw, "track_llm_call", _no_llm_trace),
        patch.object(gw.capability_router, "get_model_route", return_value=chain),
        patch.object(gw.capability_router, "health_trackers", defaultdict(MagicMock)),
        patch.object(gw.ai_gateway, "_persist_execution_record", persist),
        patch.object(gw.ai_cache, "get", AsyncMock(return_value=None)),
        patch.object(gw.ai_cache, "set", AsyncMock()),
    )


async def _run_stage(chain) -> AsyncMock:
    from app.ai import gateway as gw

    persist = AsyncMock()
    patches = _gateway_patches(gw, chain, persist)
    for p in patches:
        p.start()
    try:
        await gw.ai_gateway.generate_stage(
            stage="event_extraction",
            prompt_variables={
                "title": "t",
                "source_name": "s",
                "published_at": "unknown",
                "content": "c",
            },
        )
    finally:
        for p in patches:
            p.stop()
    return persist


@pytest.mark.parametrize(
    "error",
    [GatewayTimeoutError("deadline"), AuthenticationError("invalid key")],
    ids=["timeout", "rejected-key"],
)
async def test_a_hung_or_rejected_route_is_tried_once_then_the_next_route(error):
    hung = _failing_client(error)
    next_route = _answering_client()
    chain = [
        (hung, "k", {"provider": "openrouter", "model": DEEPSEEK}),
        (next_route, "k", {"provider": "openrouter", "model": "inception/mercury-2.5"}),
    ]

    await _run_stage(chain)

    assert hung.generate.await_count == 1, "retrying it re-bills a call that mostly fails again"
    assert next_route.generate.await_count == 1


async def test_the_gateway_parses_a_reply_with_a_leaked_end_token_first_time():
    """Any provider's reply gets the same extraction, not only OpenRouter's."""
    client = _answering_client(content=EVENT_ANSWER + LEAKED_EOS)
    chain = [(client, "k", {"provider": "bedrock", "model": "deepseek.v3.2"})]

    await _run_stage(chain)

    assert client.generate.await_count == 1


# ── Agent calls are recorded ─────────────────────────────────────────────────


async def _run_direct(chain, persist: AsyncMock | None = None) -> AsyncMock:
    from app.ai import gateway as gw

    persist = persist or AsyncMock()
    patches = _gateway_patches(gw, chain, persist)
    for p in patches:
        p.start()
    try:
        await gw.ai_gateway.execute_request(
            model=DEEPSEEK,
            stage="feedback_agent",
            messages=[{"role": "user", "content": "review"}],
            response_format=_Answer,
            story_id="00000000-0000-0000-0000-000000000001",
        )
    finally:
        for p in patches:
            p.stop()
    return persist


async def test_an_agent_call_is_written_to_the_execution_records():
    client = _answering_client(content='{"verdict": "publish", "confidence": 0.9}')
    chain = [(client, "k", {"provider": "openrouter", "model": DEEPSEEK})]

    persist = await _run_direct(chain)

    record = persist.await_args.kwargs
    assert record["stage"] == "feedback_agent"
    assert record["provider"] == "openrouter"
    assert record["model"] == DEEPSEEK
    assert record["cost"] == pytest.approx(0.0001)
    assert record["decision"] is None
    assert record["story_id"] == "00000000-0000-0000-0000-000000000001"


async def test_a_failed_agent_call_is_recorded_as_failed():
    from app.ai.errors import AIGatewayError

    hung = _failing_client(GatewayTimeoutError("deadline"))
    chain = [(hung, "k", {"provider": "openrouter", "model": DEEPSEEK})]
    persist = AsyncMock()

    with pytest.raises(AIGatewayError):
        await _run_direct(chain, persist)

    record = persist.await_args.kwargs
    assert record["stage"] == "feedback_agent"
    assert record["decision"] == "failed"
    assert record["provider"] is None


async def test_an_agent_timeout_moves_to_the_next_route():
    hung = _failing_client(GatewayTimeoutError("deadline"))
    next_route = _answering_client(content='{"verdict": "hold", "confidence": 0.5}')
    chain = [
        (hung, "k", {"provider": "openrouter", "model": DEEPSEEK}),
        (next_route, "k", {"provider": "openrouter", "model": "inception/mercury-2.5"}),
    ]

    persist = await _run_direct(chain)

    assert hung.generate.await_count == 1
    assert persist.await_args.kwargs["model"] == "inception/mercury-2.5"
    assert persist.await_args.kwargs["fallback_count"] == 1


# ── Entity linking ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "entity_type"),
    [
        ("Indus Waters Treaty", "AGREEMENT"),
        ("tramadol", "PRODUCT"),
        ("Government of Maharashtra", "GOVERNMENT_BODY"),
        ("Bharatiya Janata Party", "POLITICAL_PARTY"),
    ],
)
def test_the_deterministic_search_is_the_bare_name(name, entity_type):
    """wbsearchentities matches labels; "tramadol product" finds nothing."""
    assert entity_linker._build_deterministic_search_query(f"  {name} ", entity_type) == name


async def test_the_canonical_name_is_searched_before_the_descriptive_query():
    resolution = EntityResolution(
        canonical_name="M25 motorway",
        wikidata_search_query="M25 motorway London orbital road England",
    )
    found = {"wikidata_id": "Q19872", "description": "motorway", "label": "M25 motorway"}
    with patch.object(entity_linker, "_query_wikidata", AsyncMock(return_value=found)) as wd:
        assert await entity_linker._find_resolution_on_wikidata(resolution) == found

    assert [c.args[0] for c in wd.await_args_list] == ["M25 motorway"]


async def test_the_query_is_tried_when_the_name_finds_nothing_and_nothing_twice():
    resolution = EntityResolution(
        canonical_name="Parliament", wikidata_search_query="Parliament of India"
    )
    with patch.object(entity_linker, "_query_wikidata", AsyncMock(return_value=None)) as wd:
        result = await entity_linker._find_resolution_on_wikidata(
            resolution, already_searched="parliament"
        )

    assert result is None
    assert [c.args[0] for c in wd.await_args_list] == ["Parliament of India"], (
        "the deterministic pass already judged 'Parliament' ambiguous"
    )


@patch("app.services.entity_linker.cache_service.get", AsyncMock(return_value=None))
@patch("app.services.entity_linker.cache_service.set", AsyncMock())
async def test_an_entity_wikidata_does_not_have_is_saved_without_asking_the_agent(
    mock_db_session,
):
    no_row = MagicMock()
    no_row.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = no_row

    llm = AsyncMock(
        return_value=EntityResolution(
            canonical_name="Adluri Lakshman Kumar",
            wikidata_search_query="Adluri Lakshman Kumar Telangana minister",
            description="Telangana politician",
        )
    )
    agent = AsyncMock()
    with (
        patch("app.services.entity_linker.settings") as mock_settings,
        patch.object(entity_linker, "_query_wikidata_multi", AsyncMock(return_value=[])),
        patch.object(entity_linker, "_query_wikidata", AsyncMock(return_value=None)),
        patch.object(entity_linker, "_disambiguate_with_llm", llm),
        patch("app.agents.entity_disambiguation_agent.disambiguate_entity", agent),
    ):
        mock_settings.ENTITY_LINKING_MODE = "hybrid"
        entity = await entity_linker.link_entity(
            name="Adluri Lakshman Kumar",
            entity_type="PERSON",
            context="Minister Adluri Lakshman Kumar said...",
            session=mock_db_session,
        )

    agent.assert_not_awaited()
    assert llm.await_count == 1
    assert entity.canonical_name == "Adluri Lakshman Kumar"
    assert entity.wikidata_id is None
