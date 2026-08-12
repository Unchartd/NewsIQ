"""Regression tests for event-extraction response shapes.

Production hit:

    AIGatewayError: All providers failed for stage='event_extraction'.
    Response validation failed: 1 validation error for ArticleEventResponse
    primary_event  Field required
    input_value={'event_type': 'ACCIDENT'...}

The model returned the primary event's fields at the top level instead of
nested under `primary_event`. All the data was present, one level up.

Lifting that is normalisation — nothing is added that the model did not say.
Substituting an empty event when there is genuinely nothing to extract is
fabrication, and `_normalize_response` used to do exactly that: a missing
`primary_event` became `event_type="OTHER"` with empty actors, targets and
time, persisted as a real extraction. That is the shape 6,584 template events
took when they reached production.

Both behaviours are pinned here: lift real data, refuse to invent.
"""

import pytest
from pydantic import ValidationError

from app.services.event_service import ArticleEventResponse, event_service

# The exact payload shape from the production failure.
FLAT_EVENT = {
    "event_type": "ACCIDENT",
    "actors": ["Bus driver"],
    "targets": ["Passengers"],
    "objects": [],
    "location": "Hyderabad",
    "event_time": None,
    "numbers": {"deaths": 3},
    "confidence": 0.9,
    "entities": [{"type": "ORG", "value": "ETV Bharat"}],
}


def test_flat_event_is_lifted_into_primary_event():
    result = ArticleEventResponse.model_validate(FLAT_EVENT)
    assert result.primary_event.event_type == "ACCIDENT"
    assert result.primary_event.actors == ["Bus driver"]
    assert result.primary_event.location == "Hyderabad"
    assert result.primary_event.numbers == {"deaths": 3}


def test_flat_shape_keeps_siblings_out_of_the_event():
    """entities/secondary_events are response-level, not event fields."""
    result = ArticleEventResponse.model_validate(FLAT_EVENT)
    assert len(result.entities) == 1
    assert result.entities[0].value == "ETV Bharat"


def test_nested_shape_is_unchanged():
    nested = {
        "primary_event": {"event_type": "MERGER", "actors": ["Apple"]},
        "secondary_events": [],
        "entities": [],
    }
    assert ArticleEventResponse.model_validate(nested).primary_event.event_type == "MERGER"


@pytest.mark.parametrize(
    "payload",
    [
        {"summary": "nothing useful here", "note": "x"},
        {"secondary_events": [], "entities": []},
        {},
    ],
)
def test_responses_without_an_event_still_fail(payload):
    """The lift must be narrow enough that junk is rejected.

    A response with no event must fail so the article is retried or skipped —
    never quietly turned into an empty OTHER event.
    """
    with pytest.raises(ValidationError):
        ArticleEventResponse.model_validate(payload)


def test_normalizer_refuses_to_synthesise_a_missing_event():
    """_normalize_response must not invent an event from an empty payload."""
    with pytest.raises(ValueError, match="refusing to synthesise"):
        event_service._normalize_response({"secondary_events": [], "entities": []})


def test_normalizer_still_handles_a_real_event():
    result = event_service._normalize_response(
        {"primary_event": {"event_type": "protest", "actors": ["Union"]}, "entities": []}
    )
    assert result.primary_event.actors == ["Union"]
    # canonicalised, not passed through raw
    assert result.primary_event.event_type == result.primary_event.event_type.upper()
