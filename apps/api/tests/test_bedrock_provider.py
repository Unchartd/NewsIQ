from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIError
from pydantic import BaseModel

from app.ai.errors import AuthenticationError, RateLimitError
from app.ai.interfaces import APIKey, GatewayRequest
from app.ai.providers.bedrock import BedrockProvider


class MockResponseSchema(BaseModel):
    event_name: str
    confidence: float


def test_prepare_params():
    provider = BedrockProvider()
    request = GatewayRequest(
        model="qwen.qwen3-vl-235b-a22b-instruct",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ],
        temperature=0.7,
        response_format=MockResponseSchema,
    )

    params = provider._prepare_params(request)
    assert params["model"] == "qwen.qwen3-vl-235b-a22b-instruct"
    assert params["temperature"] == 0.7
    assert params["response_format"] == {"type": "json_object"}
    assert len(params["messages"]) == 3
    assert params["messages"][2]["role"] == "system"
    assert "JSON" in params["messages"][2]["content"]


@pytest.mark.asyncio
@patch("app.ai.providers.bedrock.AsyncOpenAI")
async def test_generate_success(mock_openai):
    mock_client = MagicMock()
    mock_choices = [
        MagicMock(message=MagicMock(content='{"event_name": "Protest", "confidence": 0.95}'))
    ]
    mock_usage = MagicMock(prompt_tokens=40, completion_tokens=20)
    mock_response = MagicMock(choices=mock_choices, usage=mock_usage)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_openai.return_value = mock_client

    provider = BedrockProvider()
    api_key = APIKey(key="mock-key", provider="bedrock")
    request = GatewayRequest(
        model="qwen.qwen3-vl-235b-a22b-instruct",
        messages=[{"role": "user", "content": "hello"}],
        response_format=MockResponseSchema,
    )

    response = await provider.generate(request, api_key)
    assert response.content == '{"event_name": "Protest", "confidence": 0.95}'
    assert response.parsed.event_name == "Protest"
    assert response.parsed.confidence == 0.95
    assert response.input_tokens == 40
    assert response.output_tokens == 20
    assert response.total_tokens == 60
    assert response.provider == "bedrock"


@pytest.mark.asyncio
@patch("app.ai.providers.bedrock.AsyncOpenAI")
async def test_generate_rate_limit_error(mock_openai):
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIError("rate limit", request=MagicMock(), body=None)
    )
    # Patch the status code of the error to be 429
    mock_client.chat.completions.create.side_effect.status_code = 429
    mock_openai.return_value = mock_client

    provider = BedrockProvider()
    api_key = APIKey(key="mock-key", provider="bedrock")
    request = GatewayRequest(
        model="qwen.qwen3-vl-235b-a22b-instruct", messages=[{"role": "user", "content": "hello"}]
    )

    with pytest.raises(RateLimitError):
        await provider.generate(request, api_key)


@pytest.mark.asyncio
@patch("app.ai.providers.bedrock.AsyncOpenAI")
async def test_generate_auth_error(mock_openai):
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIError("auth failed", request=MagicMock(), body=None)
    )
    mock_client.chat.completions.create.side_effect.status_code = 401
    mock_openai.return_value = mock_client

    provider = BedrockProvider()
    api_key = APIKey(key="mock-key", provider="bedrock")
    request = GatewayRequest(
        model="qwen.qwen3-vl-235b-a22b-instruct", messages=[{"role": "user", "content": "hello"}]
    )

    with pytest.raises(AuthenticationError):
        await provider.generate(request, api_key)
