import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from google import genai as google_genai
from google.genai import types
from pydantic import BaseModel

from app.ai.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from app.ai.interfaces import AIProvider, APIKey, GatewayRequest, GatewayResponse, HealthStatus

logger = logging.getLogger(__name__)


def remove_additional_properties(schema: Any) -> Any:
    """Recursively remove 'additionalProperties' keys from JSON Schema dicts."""
    if isinstance(schema, dict):
        schema.pop("additionalProperties", None)
        return {k: remove_additional_properties(v) for k, v in schema.items()}
    elif isinstance(schema, list):
        return [remove_additional_properties(item) for item in schema]
    return schema


class GeminiProvider(AIProvider):
    """Google Gemini Client Provider using the google-genai SDK."""

    def _prepare_params(self, request: GatewayRequest) -> dict[str, Any]:
        """Convert standard GatewayRequest parameters to Gemini SDK generate_content parameters."""
        contents = []
        system_instruction = None

        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "assistant":
                contents.append(
                    types.Content(role="model", parts=[types.Part.from_text(text=content)])
                )
            else:
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=content)])
                )

        config_args: dict[str, Any] = {
            "temperature": request.temperature,
        }
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        if request.response_format:
            config_args["response_mime_type"] = "application/json"
            if isinstance(request.response_format, type) and issubclass(
                request.response_format, BaseModel
            ):
                schema_dict = request.response_format.model_json_schema()
                config_args["response_schema"] = remove_additional_properties(schema_dict)
            elif isinstance(request.response_format, dict):
                # Skip OpenAI-style {"type": "json_object"} parameters
                if (
                    request.response_format.get("type") == "json_object"
                    and len(request.response_format) == 1
                ):
                    pass
                else:
                    config_args["response_schema"] = remove_additional_properties(
                        request.response_format
                    )

        config = types.GenerateContentConfig(**config_args)
        return {"contents": contents, "config": config}

    def _handle_exception(self, e: Exception) -> Exception:
        """Map SDK errors to custom gateway exceptions."""
        err_msg = str(e)
        err_lower = err_msg.lower()
        if "401" in err_lower or "api key not valid" in err_lower or "invalid api key" in err_lower or "403" in err_lower:
            return AuthenticationError(f"Gemini authentication failed: {err_msg}")
        elif "429" in err_lower or "rate limit" in err_lower or "quota" in err_lower or "resource exhausted" in err_lower or "too many requests" in err_lower:
            return RateLimitError(f"Gemini rate limit exceeded: {err_msg}")
        elif "timeout" in err_lower or "deadline exceeded" in err_lower:
            return TimeoutError(f"Gemini request timed out: {err_msg}")
        else:
            return ProviderUnavailableError(f"Gemini provider error: {err_msg}")

    async def generate(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        t0 = time.perf_counter()
        try:
            client = google_genai.Client(api_key=api_key.key)
            params = self._prepare_params(request)

            response = await client.aio.models.generate_content(
                model=request.model,
                contents=params["contents"],
                config=params["config"]
            )
            latency_ms = (time.perf_counter() - t0) * 1000

            input_tokens = 0
            output_tokens = 0
            if getattr(response, "usage_metadata", None) is not None:
                meta = response.usage_metadata
                if meta is not None:
                    input_tokens = getattr(meta, "prompt_token_count", 0) or 0
                    output_tokens = getattr(meta, "candidates_token_count", 0) or 0

            content = response.text or ""
            parsed = None

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
                    logger.warning("Gemini parsing failed: %s, content: %s", parse_err, content)

            return GatewayResponse(
                content=content,
                parsed=parsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                provider="gemini",
                model=request.model,
                key_used=api_key.get_masked(),
            )
        except Exception as e:
            raise self._handle_exception(e)

    async def stream(self, request: GatewayRequest, api_key: APIKey) -> AsyncGenerator[str, None]:
        try:
            client = google_genai.Client(api_key=api_key.key)
            params = self._prepare_params(request)

            response_stream = await client.aio.models.generate_content_stream(
                model=request.model,
                contents=params["contents"],
                config=params["config"]
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise self._handle_exception(e)

    async def health(self, api_key: APIKey) -> HealthStatus:
        t0 = time.perf_counter()
        try:
            client = google_genai.Client(api_key=api_key.key)
            # Make a lightweight call to verify key and latency
            await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=5, temperature=0.0)
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            return HealthStatus(
                healthy=True,
                latency_ms=latency_ms,
                supported_models=["gemini-2.5-flash", "gemini-2.5-pro", "text-embedding-004"]
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
            client = google_genai.Client(api_key=api_key.key)
            response = client.models.embed_content(
                model="text-embedding-004",
                contents=text,
                config={"task_type": "RETRIEVAL_DOCUMENT"},
            )
            if response.embeddings:
                raw_val = response.embeddings[0].values
                if raw_val is not None:
                    # Target dimension is 768
                    return raw_val[:768]
            raise ValueError("No embeddings returned from Gemini API")
        except Exception as e:
            raise self._handle_exception(e)
