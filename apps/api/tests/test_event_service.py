from unittest.mock import AsyncMock, patch

import pytest

from app.llm_gateway.base_provider import GatewayResponse
from app.services.event_service import ArticleEventResponse, ExtractedEvent, event_service
from app.services.event_taxonomy import (
    canonicalize_event_type,
    get_parent_type,
)


@pytest.fixture(autouse=True)
def disable_cache():
    with (
        patch("app.services.pipeline_cache.pipeline_cache.get", new_callable=AsyncMock) as mock_get,
        patch("app.services.pipeline_cache.pipeline_cache.set", new_callable=AsyncMock) as mock_set,
    ):
        mock_get.return_value = None
        yield


def test_event_taxonomy():
    """Verify that event taxonomy and synonym mapping work correctly."""
    # Test canonicalizing exact taxonomy keys
    assert canonicalize_event_type("ATTACK") == "ATTACK"
    assert canonicalize_event_type("MISSILE_STRIKE") == "MISSILE_STRIKE"

    # Test synonym mapping
    assert canonicalize_event_type("arrested") == "DETENTION"
    assert canonicalize_event_type("missile strike") == "MISSILE_STRIKE"
    assert canonicalize_event_type("laid off") == "LAYOFF"

    # Test partial / case synonym match
    assert canonicalize_event_type("Airstrike") == "ATTACK"
    assert canonicalize_event_type("detained") == "DETENTION"

    # Test parent resolution
    assert get_parent_type("MISSILE_STRIKE") == "ATTACK"
    assert get_parent_type("ARREST") == "DETENTION"
    assert get_parent_type("ATTACK") == "ATTACK"
    assert get_parent_type("OTHER") == "OTHER"

    # Test default fallback
    assert canonicalize_event_type("") == "OTHER"
    assert canonicalize_event_type(None) == "OTHER"
    assert canonicalize_event_type("random_nonexistent_event") == "RANDOM_NONEXISTENT_EVENT"


@pytest.mark.asyncio
async def test_detect_event_time_conflict():
    """Verify event time conflict detection heuristic."""
    # No events
    assert await event_service.detect_event_time_conflict([]) is False

    # Single event
    event1 = ExtractedEvent(
        event_type="ATTACK",
        actors=["Actor 1"],
        location="Location 1",
        event_time="2026-06-20T12:00:00Z",
    )
    assert await event_service.detect_event_time_conflict([event1]) is False

    # Multiple events with same time
    event2 = ExtractedEvent(
        event_type="ATTACK",
        actors=["Actor 2"],
        location="Location 1",
        event_time="2026-06-20T12:00:00Z",
    )
    assert await event_service.detect_event_time_conflict([event1, event2]) is False

    # Multiple events with different times
    event3 = ExtractedEvent(
        event_type="ATTACK",
        actors=["Actor 3"],
        location="Location 1",
        event_time="2026-06-21T12:00:00Z",
    )
    assert await event_service.detect_event_time_conflict([event1, event3]) is True

    # Empty or null event times should be ignored
    event_null = ExtractedEvent(
        event_type="ATTACK",
        actors=["Actor 4"],
        location="Location 1",
        event_time=None,
    )
    assert await event_service.detect_event_time_conflict([event1, event_null]) is False


@pytest.mark.asyncio
@patch("app.ai.gateway.ai_gateway.generate_stage")
async def test_extract_events_gateway_parsed_success(mock_generate):
    """Verify that event extraction succeeds using LLM Gateway returning parsed response."""
    expected_response = ArticleEventResponse(
        primary_event=ExtractedEvent(
            event_type="DETENTION",
            actors=["Police"],
            targets=["Suspect"],
            location="London",
            event_time="2026-06-20T10:00:00Z",
            confidence=0.9,
        ),
        secondary_events=[],
    )
    mock_response = GatewayResponse(
        content="",
        parsed=expected_response,
        provider="google",
        model="gemini-2.5-flash-lite",
    )
    mock_generate.return_value = mock_response

    res = await event_service.extract_events(
        title="Police arrested suspect",
        content="London police arrested the suspect on Saturday.",
    )
    assert res.primary_event.event_type == "DETENTION"
    assert "Police" in res.primary_event.actors
    assert res.primary_event.confidence == 0.9
    mock_generate.assert_called_once()


@pytest.mark.asyncio
@patch("app.ai.gateway.ai_gateway.generate_stage")
async def test_extract_events_gateway_json_string_success(mock_generate):
    """Verify that event extraction succeeds using LLM Gateway returning raw JSON string."""
    mock_response = GatewayResponse(
        content='{"primary_event": {"event_type": "ELECTION", "actors": ["Voters"], "targets": [], "location": "France", "event_time": "2026-06-20T00:00:00Z", "confidence": 0.85}, "secondary_events": []}',
        parsed=None,
        provider="openai",
        model="gpt-4o-mini",
    )
    mock_generate.return_value = mock_response

    res = await event_service.extract_events(
        title="France Elections",
        content="Voters in France cast their ballots.",
    )
    assert res.primary_event.event_type == "ELECTION"
    assert "Voters" in res.primary_event.actors
    mock_generate.assert_called_once()


@pytest.mark.asyncio
@patch("app.ai.gateway.ai_gateway.generate_stage")
async def test_extract_events_gateway_failure_propagates_exception(mock_generate):
    """Verify that event extraction raises the exception when gateway fails."""
    mock_generate.side_effect = Exception("Gateway Timeout")

    with pytest.raises(Exception, match="Gateway Timeout"):
        await event_service.extract_events(
            title="Failed API test",
            content="Some news content.",
        )
    mock_generate.assert_called_once()
