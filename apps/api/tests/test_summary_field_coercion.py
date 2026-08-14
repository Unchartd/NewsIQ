"""Regression tests for identical one-line/short/detailed story summaries.

Production had 4 of 9 summarised stories with all three summary columns
byte-identical (238-1439 chars each), so the tab labelled "1-line summary"
rendered a full paragraph.

Cause: when the model returned a single "summary" field instead of the
three-tier fields, clean_json_for_schema copied that one value into
one_line_summary, short_summary AND detailed_summary. Schema validation then
passed, so the gateway never retried — three summaries were reported where the
model had produced one.
"""

from app.ai.gateway import clean_json_for_schema
from app.services.ai_service import StorySummaryResponse


def test_lone_summary_does_not_populate_all_three_fields():
    """A single 'summary' must not be fanned out into three identical fields."""
    cleaned = clean_json_for_schema(
        {
            "headline": "H",
            "summary": "A comprehensive paragraph about the event.",
            "key_facts": ["a"],
        },
        StorySummaryResponse,
    )

    assert cleaned.get("detailed_summary") == "A comprehensive paragraph about the event."
    assert not cleaned.get("one_line_summary"), (
        "a one-line summary was fabricated from the detailed prose — "
        "this is what put a full paragraph behind the '1-line' tab"
    )
    assert not cleaned.get("short_summary"), (
        "a short summary was fabricated from the detailed prose"
    )


def test_fabricated_summaries_would_fail_validation_and_force_a_retry():
    """Leaving the fields absent must fail validation so the gateway retries."""
    import pytest
    from pydantic import ValidationError

    cleaned = clean_json_for_schema(
        {"headline": "H", "summary": "One blob.", "key_facts": ["a"], "category": "world"},
        StorySummaryResponse,
    )

    with pytest.raises(ValidationError):
        StorySummaryResponse.model_validate(cleaned)


def test_model_supplied_three_tier_summaries_are_preserved():
    """The correct path — three distinct summaries — must pass through untouched."""
    payload = {
        "headline": "H",
        "one_line_summary": "One sentence.",
        "short_summary": "A short paragraph of three sentences.",
        "detailed_summary": "A much longer multi-paragraph treatment.",
        "key_facts": ["a"],
        "category": "world",
    }
    cleaned = clean_json_for_schema(dict(payload), StorySummaryResponse)

    for field in ("one_line_summary", "short_summary", "detailed_summary"):
        assert cleaned[field] == payload[field]


def test_summary_prompt_demands_three_distinct_summaries():
    """The prompt must actually ask for the three fields, not one 'summary'."""
    from pathlib import Path

    import app.ai.prompts as prompts_pkg

    text = (Path(prompts_pkg.__file__).parent / "summary_generation.yaml").read_text(
        encoding="utf-8"
    )

    for field in ("one_line_summary", "short_summary", "detailed_summary"):
        assert field in text, f"the prompt never names {field}, so models omit it"


def _valid_payload(**overrides):
    payload = {
        "headline": "Panel finds judge guilty of misconduct",
        "one_line_summary": "An inquiry panel found the judge guilty of misconduct.",
        "short_summary": "An inquiry panel found the judge guilty. " * 3,
        "detailed_summary": "An inquiry panel found the judge guilty of misconduct. " * 6,
        "key_facts": ["a"],
        "category": "politics",
    }
    payload.update(overrides)
    return payload


def test_schema_echo_is_rejected():
    """Production published a story whose every field was the word "string"."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StorySummaryResponse.model_validate(
            {
                "headline": "string",
                "one_line_summary": "string",
                "short_summary": "string",
                "detailed_summary": "string",
                "key_facts": ["string"],
                "category": "string",
            }
        )


def test_three_identical_summaries_are_rejected_even_when_all_fields_present():
    """The coercion fix only covered a lone 'summary'; a model can still repeat itself."""
    import pytest
    from pydantic import ValidationError

    same = "The inquiry panel found the judge guilty of misconduct in a written report. " * 3
    with pytest.raises(ValidationError):
        StorySummaryResponse.model_validate(
            _valid_payload(one_line_summary=same, short_summary=same, detailed_summary=same)
        )


def test_a_paragraph_behind_the_one_line_tab_is_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StorySummaryResponse.model_validate(_valid_payload(one_line_summary="word " * 200))


def test_a_genuinely_tiered_summary_still_validates():
    """The floors must not reject real output."""
    assert StorySummaryResponse.model_validate(_valid_payload()).category == "politics"


def test_no_stage_prefers_the_quota_exhausted_model():
    """gemini-3.1-flash-lite measured 1598 rate-limit errors over 1026 calls."""
    from pathlib import Path

    import app.ai.prompts as prompts_pkg

    offenders = [
        p.name
        for p in Path(prompts_pkg.__file__).parent.glob("*.yaml")
        if 'preferred_model: "gemini-3.1-flash-lite"' in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"these stages lead with the exhausted model: {offenders}"
