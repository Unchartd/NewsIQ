"""Bedrock must be shown the schema it is asked to match.

The Mantle endpoint's json_object mode takes no schema parameter — the model
only knows the shape it is told about in the prompt. The old instruction said
"Respond in valid JSON format matching the schema" without including one, so
the models invented field names or echoed placeholders verbatim:

    {"reasoning": "step-by-step reasoning", "is_contradiction": true,
     "explanation": "brief explanation"}

Measured over the first two hours of Bedrock carrying contradiction_detection
after the #136 fallbacks went live: 1,351 of 1,352 responses failed schema
validation — paid calls, all discarded, ~6 per candidate through the retry
chain.
"""

from app.ai.interfaces import GatewayRequest
from app.ai.providers.bedrock import BedrockProvider
from app.services.contradiction_service import ContradictionResolution


def _params(response_format):
    provider = BedrockProvider(base_url="https://example.invalid/v1")
    request = GatewayRequest(
        model="deepseek.v3.2",
        messages=[{"role": "user", "content": "Compare these two reports."}],
        temperature=0.1,
        response_format=response_format,
        stage="contradiction_detection",
        timeout=30.0,
    )
    return provider._prepare_params(request)


def test_schema_fields_are_spelled_out_in_the_prompt():
    params = _params(ContradictionResolution)
    appended = params["messages"][-1]["content"]

    for field in ("is_contradiction", "description", "confidence"):
        assert f'"{field}"' in appended, f"schema field {field} missing from instruction"
    assert "EXACTLY these" in appended
    assert params["response_format"] == {"type": "json_object"}


def test_instruction_is_added_even_when_the_prompt_mentions_json():
    """The old code skipped its (schema-less) instruction whenever any message
    contained the substring 'json' — mentioning the word is not the same as
    spelling out the shape."""
    provider = BedrockProvider(base_url="https://example.invalid/v1")
    request = GatewayRequest(
        model="qwen.qwen3-vl-235b-a22b-instruct",
        messages=[{"role": "user", "content": "Return JSON describing the conflict."}],
        temperature=0.1,
        response_format=ContradictionResolution,
        stage="contradiction_detection",
        timeout=30.0,
    )
    params = provider._prepare_params(request)
    assert '"is_contradiction"' in params["messages"][-1]["content"]


def test_the_observed_placeholder_echo_fails_validation():
    """The exact production response shape must not validate — it is what the
    schema instruction exists to prevent."""
    import pydantic
    import pytest

    with pytest.raises(pydantic.ValidationError):
        ContradictionResolution.model_validate(
            {
                "reasoning": "step-by-step reasoning",
                "is_contradiction": True,
                "explanation": "brief explanation",
            }
        )
