import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel

from app.ai.embedding_utils import EMBEDDING_DIM, l2_normalize
from app.ai.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from app.ai.interfaces import AIProvider, APIKey, GatewayRequest, GatewayResponse, HealthStatus
from app.core.config import settings

logger = logging.getLogger(__name__)


class BedrockProvider(AIProvider):
    """AWS Bedrock Provider using the OpenAI-compatible Mantle API endpoint."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (
            base_url
            or settings.AWS_BEDROCK_BASE_URL
            or "https://bedrock-mantle.us-east-1.api.aws/v1"
        )

    def _prepare_params(self, request: GatewayRequest) -> dict[str, Any]:
        """Convert GatewayRequest to OpenAI completion params."""
        messages = list(request.messages)
        params: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }

        # Handle JSON / Structured Outputs.
        #
        # Unlike Gemini, the Mantle endpoint's json_object mode does not take
        # a schema — the model only knows the shape it is told about in the
        # prompt. This used to say "Respond in valid JSON format matching the
        # schema" WITHOUT ever including the schema, so the models invented
        # field names: measured over the first two hours of Bedrock carrying
        # contradiction_detection, 1,351 of 1,352 responses failed validation,
        # most echoing literal placeholders like {"reasoning": "step-by-step
        # reasoning", "explanation": "brief explanation"}.
        if request.response_format:
            params["response_format"] = {"type": "json_object"}
            schema_instruction = "Respond with a single valid JSON object."
            if isinstance(request.response_format, type) and issubclass(
                request.response_format, BaseModel
            ):
                schema = request.response_format.model_json_schema()
                required = schema.get("required", [])
                fields = []
                for key, prop in schema.get("properties", {}).items():
                    kind = prop.get("type", "any")
                    desc = prop.get("description", "")
                    req = "required" if key in required else "optional"
                    fields.append(f'  "{key}" ({kind}, {req}): {desc}')
                schema_instruction = (
                    "Respond with ONLY a single JSON object using EXACTLY these "
                    "keys — no other keys, no prose, no markdown fences:\n" + "\n".join(fields)
                )
            params["messages"] = messages + [{"role": "system", "content": schema_instruction}]

        return params

    def _handle_exception(self, e: Exception) -> Exception:
        if isinstance(e, APITimeoutError):
            return TimeoutError(f"Bedrock request timed out: {e}")
        elif isinstance(e, APIError):
            status = getattr(e, "status_code", None)
            if status == 401:
                return AuthenticationError(f"Bedrock authentication failed: {e}")
            elif status == 429:
                return RateLimitError(f"Bedrock rate limit exceeded: {e}")
            else:
                return ProviderUnavailableError(f"Bedrock unavailable: {e}")
        return ProviderUnavailableError(f"Bedrock error: {str(e)}")

    async def generate(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        t0 = time.perf_counter()
        try:
            client = AsyncOpenAI(api_key=api_key.key, base_url=self.base_url)
            params = self._prepare_params(request)

            response = await client.chat.completions.create(**params, timeout=request.timeout)
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
                    logger.warning("Bedrock parsing failed: %s, content: %s", parse_err, content)

            return GatewayResponse(
                content=content,
                parsed=parsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                provider="bedrock",
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
                **params, stream=True, timeout=request.timeout
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
                model="qwen.qwen3-vl-235b-a22b-instruct",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                temperature=0.0,
                timeout=5.0,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            return HealthStatus(
                healthy=True,
                latency_ms=latency_ms,
                supported_models=["qwen.qwen3-vl-235b-a22b-instruct", "qwen.qwen3-32b"],
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            return HealthStatus(
                healthy=False, latency_ms=latency_ms, supported_models=[], error=str(e)
            )

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken

            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            return len(text) // 4

    async def embeddings(self, text: str, api_key: APIKey, model: str | None = None) -> list[float]:
        try:
            model_name = model or "amazon.titan-embed-text-v2:0"
            client = AsyncOpenAI(api_key=api_key.key, base_url=self.base_url)
            response = await client.embeddings.create(input=[text], model=model_name)
            raw = list(response.data[0].embedding)
            # Refuse rather than truncate — see the NVIDIA provider for the
            # reasoning. Mixing embedding spaces in one collection is silent and
            # unrecoverable without model provenance on every point.
            if len(raw) != EMBEDDING_DIM:
                raise ValueError(
                    f"Bedrock model '{model_name}' returned {len(raw)} dimensions, "
                    f"but the pipeline requires {EMBEDDING_DIM}. Titan models accept a "
                    "dimensions parameter — configure it rather than truncating."
                )
            return l2_normalize(raw)
        except Exception as e:
            raise self._handle_exception(e)
