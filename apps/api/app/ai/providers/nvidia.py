import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel

from app.ai.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from app.ai.interfaces import AIProvider, APIKey, GatewayRequest, GatewayResponse, HealthStatus

logger = logging.getLogger(__name__)


class NvidiaProvider(AIProvider):
    """NVIDIA NIM Client Provider using the AsyncOpenAI SDK wrapper."""

    def __init__(self, base_url: str = "https://integrate.api.nvidia.com/v1") -> None:
        self.base_url = base_url

    def _prepare_params(self, request: GatewayRequest) -> dict[str, Any]:
        """Convert GatewayRequest to OpenAI completion params."""
        messages = list(request.messages)
        params: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }

        # Handle JSON / Structured Outputs
        if request.response_format:
            params["response_format"] = {"type": "json_object"}
            # Ensure "json" is explicitly mentioned in system/user messages for JSON mode compliance
            has_json = any("json" in str(m.get("content", "")).lower() for m in messages)
            if not has_json:
                params["messages"] = messages + [
                    {"role": "system", "content": "Respond in valid JSON format matching the schema."}
                ]

        return params

    def _handle_exception(self, e: Exception) -> Exception:
        if isinstance(e, APITimeoutError):
            return TimeoutError(f"NVIDIA request timed out: {e}")
        elif isinstance(e, APIError):
            status = getattr(e, "status_code", None)
            if status == 401:
                return AuthenticationError(f"NVIDIA authentication failed: {e}")
            elif status == 429:
                return RateLimitError(f"NVIDIA rate limit exceeded: {e}")
            else:
                return ProviderUnavailableError(f"NVIDIA unavailable: {e}")
        return ProviderUnavailableError(f"NVIDIA error: {str(e)}")

    async def generate(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        t0 = time.perf_counter()
        try:
            client = AsyncOpenAI(api_key=api_key.key, base_url=self.base_url)
            params = self._prepare_params(request)

            response = await client.chat.completions.create(
                **params,
                timeout=request.timeout
            )
            latency_ms = (time.perf_counter() - t0) * 1000

            choice = response.choices[0]
            content = choice.message.content or ""
            parsed = None

            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            if request.response_format and content:
                try:
                    data = json.loads(content)
                    if isinstance(request.response_format, type) and issubclass(
                        request.response_format, BaseModel
                    ):
                        parsed = request.response_format.model_validate(data)
                    else:
                        parsed = data
                except Exception as parse_err:
                    logger.warning("NVIDIA parsing failed: %s, content: %s", parse_err, content)

            return GatewayResponse(
                content=content,
                parsed=parsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                provider="nvidia",
                model=request.model,
                key_used=api_key.get_masked(),
            )
        except Exception as e:
            raise self._handle_exception(e)

    async def stream(self, request: GatewayRequest, api_key: APIKey) -> AsyncGenerator[str, None]:
        try:
            client = AsyncOpenAI(api_key=api_key.key, base_url=self.base_url)
            params = self._prepare_params(request)

            response_stream = await client.chat.completions.create(
                **params,
                stream=True,
                timeout=request.timeout
            )
            async for chunk in response_stream:
                choice = chunk.choices[0]
                if choice.delta.content:
                    yield choice.delta.content
        except Exception as e:
            raise self._handle_exception(e)

    async def health(self, api_key: APIKey) -> HealthStatus:
        t0 = time.perf_counter()
        try:
            client = AsyncOpenAI(api_key=api_key.key, base_url=self.base_url)
            # Lightweight verification call
            await client.chat.completions.create(
                model="deepseek-ai/deepseek-v4-flash",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                temperature=0.0,
                timeout=5.0
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            return HealthStatus(
                healthy=True,
                latency_ms=latency_ms,
                supported_models=["deepseek-ai/deepseek-v4-flash", "deepseek-ai/deepseek-v4-pro"]
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            return HealthStatus(
                healthy=False,
                latency_ms=latency_ms,
                supported_models=[],
                error=str(e)
            )

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            return len(text) // 4

    async def embeddings(self, text: str, api_key: APIKey) -> list[float]:
        try:
            client = AsyncOpenAI(api_key=api_key.key, base_url=self.base_url)
            # For NVIDIA, we use their default/configured embed model, or fallback
            response = await client.embeddings.create(
                input=[text],
                model="nvidia/llama-3.2-nv-embedqa-4b-v1"
            )
            raw = response.data[0].embedding
            return raw[:768]
        except Exception as e:
            raise self._handle_exception(e)
