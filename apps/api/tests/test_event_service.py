"""Unit tests for the event service and event taxonomy."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.event_service import event_service, ExtractedEvent, ArticleEventResponse
from app.services.event_taxonomy import (
    canonicalize_event_type,
    get_parent_type,
    get_all_canonical_types,
)


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
@patch("app.services.event_service.event_service._extract_with_gemini")
async def test_extract_events_gemini_success(mock_gemini):
    """Verify that event extraction succeeds using Gemini when enabled."""
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
    mock_gemini.return_value = expected_response

    # Force enable Gemini
    with patch.object(event_service, "gemini_enabled", True):
        res = await event_service.extract_events(
            title="Police arrested suspect",
            content="London police arrested the suspect on Saturday.",
        )
        assert res.primary_event.event_type == "DETENTION"
        assert "Police" in res.primary_event.actors
        assert res.primary_event.confidence == 0.9
        mock_gemini.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.event_service.event_service._extract_with_gemini")
@patch("app.services.event_service.event_service._extract_with_openai")
async def test_extract_events_fallback_to_openai(mock_openai, mock_gemini):
    """Verify that event extraction falls back to OpenAI when Gemini fails."""
    mock_gemini.side_effect = Exception("Gemini Quota Exceeded")
    
    expected_response = ArticleEventResponse(
        primary_event=ExtractedEvent(
            event_type="ELECTION",
            actors=["Voters"],
            targets=[],
            location="France",
            event_time="2026-06-20T00:00:00Z",
            confidence=0.85,
        ),
        secondary_events=[],
    )
    mock_openai.return_value = expected_response

    # Force enable both
    with patch.object(event_service, "gemini_enabled", True), \
         patch.object(event_service, "openai_enabled", True), \
         patch.object(event_service, "_openai_client", MagicMock()):
        
        res = await event_service.extract_events(
            title="France Elections",
            content="Voters in France cast their ballots.",
        )
        assert res.primary_event.event_type == "ELECTION"
        assert "Voters" in res.primary_event.actors
        mock_gemini.assert_called_once()
        mock_openai.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.event_service.event_service._extract_with_gemini")
@patch("app.services.event_service.event_service._extract_with_openai")
async def test_extract_events_fallback_to_mock(mock_openai, mock_gemini):
    """Verify that event extraction falls back to mock when both LLMs fail."""
    mock_gemini.side_effect = Exception("Gemini Error")
    mock_openai.side_effect = Exception("OpenAI Error")

    with patch.object(event_service, "gemini_enabled", True), \
         patch.object(event_service, "openai_enabled", True), \
         patch.object(event_service, "_openai_client", MagicMock()):
        
        res = await event_service.extract_events(
            title="Failed API test",
            content="Some news content.",
        )
        assert res.primary_event.event_type == "OTHER"
        assert "[Mock] Unknown Actor" in res.primary_event.actors
        assert res.primary_event.confidence == 0.1
