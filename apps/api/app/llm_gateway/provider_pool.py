import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel
from google import genai as google_genai
from google.genai import types
from openai import AsyncOpenAI, OpenAI

from app.core.config import settings
from app.llm_gateway.base_provider import BaseLLMProvider, GatewayRequest, GatewayResponse, APIKey

logger = logging.getLogger(__name__)

class APIKeyPool:
    """Manages rotating and cooling down API keys per provider."""

    def __init__(self) -> None:
        self.pools: Dict[str, List[APIKey]] = {}
        self._load_keys()

    def _load_keys(self) -> None:
        """Load API keys from configuration settings."""
        # 1. Google Gemini Keys
        gemini_keys = []
        gemini_env = settings.GEMINI_API_KEY_SYNTH or settings.GEMINI_API_KEY or ""
        # Support comma-separated keys for rotation
        for k in [k.strip() for k in gemini_env.split(",") if k.strip()]:
            gemini_keys.append(APIKey(key=k, provider="google", requests_per_minute=15, requests_per_day=1500))
        self.pools["google"] = gemini_keys

        # 2. OpenAI Keys
        openai_keys = []
        openai_env = settings.OPENAI_API_KEY or ""
        for k in [k.strip() for k in openai_env.split(",") if k.strip()]:
            openai_keys.append(APIKey(key=k, provider="openai", requests_per_minute=3, requests_per_day=200))
        self.pools["openai"] = openai_keys

        # 3. Groq Keys (falls back to OpenAI-compatible environment config or mock)
        groq_keys = []
        groq_env = os.environ.get("GROQ_API_KEY", "")
        for k in [k.strip() for k in groq_env.split(",") if k.strip()]:
            groq_keys.append(APIKey(key=k, provider="groq", requests_per_minute=30, requests_per_day=14400))
        self.pools["groq"] = groq_keys

        # 4. Fallbacks / Mock keys
        self.pools["mock"] = [APIKey(key="mock-key-1", provider="mock", requests_per_minute=1000, requests_per_day=100000)]

        logger.info(
            "APIKeyPool loaded: google=%d, openai=%d, groq=%d, mock=%d keys.",
            len(self.pools["google"]), len(self.pools["openai"]), len(self.pools["groq"]), len(self.pools["mock"])
        )

    def get_keys(self, provider: str) -> List[APIKey]:
        """Return the key pool for a provider."""
        return self.pools.get(provider, [])


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Client Provider using the new google-genai SDK."""

    def _prepare_params(self, request: GatewayRequest) -> Dict[str, Any]:
        """Convert standard GatewayRequest parameters to Gemini SDK generate_content parameters."""
        contents = []
        system_instruction = None

        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))
            else:
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))

        config_args = {
            "temperature": request.temperature,
        }
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        if request.response_format:
            config_args["response_mime_type"] = "application/json"
            if isinstance(request.response_format, type) and issubclass(request.response_format, BaseModel):
                config_args["response_schema"] = request.response_format
            elif isinstance(request.response_format, dict):
                config_args["response_schema"] = request.response_format

        config = types.GenerateContentConfig(**config_args)
        return {"contents": contents, "config": config}

    async def execute(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        client = google_genai.Client(api_key=api_key.key)
        params = self._prepare_params(request)

        start_time = datetime.utcnow()
        try:
            response = await client.aio.models.generate_content(
                model=request.model,
                contents=params["contents"],
                config=params["config"]
            )
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            input_tokens = 0
            output_tokens = 0
            if getattr(response, "usage_metadata", None):
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            content = response.text or ""
            parsed = None
            if request.response_format and content:
                try:
                    data = json.loads(content)
                    if isinstance(request.response_format, type) and issubclass(request.response_format, BaseModel):
                        parsed = request.response_format.model_validate(data)
                    else:
                        parsed = data
                except Exception as parse_err:
                    logger.warning("Gemini parsing failed: %s, raw content: %s", parse_err, content)

            return GatewayResponse(
                content=content,
                parsed=parsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                provider="google",
                model=request.model,
                key_used=api_key.get_masked()
            )
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return GatewayResponse(
                content="",
                provider="google",
                model=request.model,
                key_used=api_key.get_masked(),
                error=str(e),
                latency_ms=latency_ms
            )

    def execute_sync(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        client = google_genai.Client(api_key=api_key.key)
        params = self._prepare_params(request)

        start_time = datetime.utcnow()
        try:
            response = client.models.generate_content(
                model=request.model,
                contents=params["contents"],
                config=params["config"]
            )
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            input_tokens = 0
            output_tokens = 0
            if getattr(response, "usage_metadata", None):
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            content = response.text or ""
            parsed = None
            if request.response_format and content:
                try:
                    data = json.loads(content)
                    if isinstance(request.response_format, type) and issubclass(request.response_format, BaseModel):
                        parsed = request.response_format.model_validate(data)
                    else:
                        parsed = data
                except Exception as parse_err:
                    logger.warning("Gemini sync parsing failed: %s, raw content: %s", parse_err, content)

            return GatewayResponse(
                content=content,
                parsed=parsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                provider="google",
                model=request.model,
                key_used=api_key.get_masked()
            )
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return GatewayResponse(
                content="",
                provider="google",
                model=request.model,
                key_used=api_key.get_masked(),
                error=str(e),
                latency_ms=latency_ms
            )


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Client Provider, also acts as adapter for generic OpenAI-compatible endpoints."""

    def __init__(self, provider_name: str = "openai", base_url: Optional[str] = None) -> None:
        self.provider_name = provider_name
        self.base_url = base_url

    def _prepare_params(self, request: GatewayRequest) -> Dict[str, Any]:
        """Prepare OpenAI API parameters, accommodating Pydantic structured formats."""
        params: Dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
        }

        # Handle tools if provided
        if request.tools:
            params["tools"] = request.tools
            if request.tool_choice:
                params["tool_choice"] = request.tool_choice

        return params

    async def execute(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        client = AsyncOpenAI(api_key=api_key.key, base_url=self.base_url)
        params = self._prepare_params(request)

        start_time = datetime.utcnow()
        try:
            # If Pydantic output schema is requested, use structured output parsing
            if request.response_format and isinstance(request.response_format, type) and issubclass(request.response_format, BaseModel):
                response = await client.beta.chat.completions.parse(
                    **params,
                    response_format=request.response_format
                )
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                choice = response.choices[0]
                content = choice.message.content or ""
                parsed = choice.message.parsed

                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0
            else:
                if request.response_format:
                    params["response_format"] = request.response_format
                response = await client.chat.completions.create(**params)
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                choice = response.choices[0]
                content = choice.message.content or ""
                parsed = None

                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0

                if request.response_format and content:
                    try:
                        parsed = json.loads(content)
                    except Exception:
                        pass

            return GatewayResponse(
                content=content,
                parsed=parsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                provider=self.provider_name,
                model=request.model,
                key_used=api_key.get_masked()
            )
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return GatewayResponse(
                content="",
                provider=self.provider_name,
                model=request.model,
                key_used=api_key.get_masked(),
                error=str(e),
                latency_ms=latency_ms
            )

    def execute_sync(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        client = OpenAI(api_key=api_key.key, base_url=self.base_url)
        params = self._prepare_params(request)

        start_time = datetime.utcnow()
        try:
            if request.response_format and isinstance(request.response_format, type) and issubclass(request.response_format, BaseModel):
                response = client.beta.chat.completions.parse(
                    **params,
                    response_format=request.response_format
                )
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                choice = response.choices[0]
                content = choice.message.content or ""
                parsed = choice.message.parsed

                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0
            else:
                if request.response_format:
                    params["response_format"] = request.response_format
                response = client.chat.completions.create(**params)
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                choice = response.choices[0]
                content = choice.message.content or ""
                parsed = None

                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0

                if request.response_format and content:
                    try:
                        parsed = json.loads(content)
                    except Exception:
                        pass

            return GatewayResponse(
                content=content,
                parsed=parsed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                provider=self.provider_name,
                model=request.model,
                key_used=api_key.get_masked()
            )
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return GatewayResponse(
                content="",
                provider=self.provider_name,
                model=request.model,
                key_used=api_key.get_masked(),
                error=str(e),
                latency_ms=latency_ms
            )


class MockProvider(BaseLLMProvider):
    """Mock Provider that yields deterministic structured or text content based on request configurations."""

    def _generate_mock_output(self, request: GatewayRequest) -> GatewayResponse:
        content = "Mock response content."
        parsed = None
        
        # Populate schema dummy if requested
        if request.response_format:
            if isinstance(request.response_format, type) and issubclass(request.response_format, BaseModel):
                schema = request.response_format
                fields = {}
                
                # Check messages for keywords to return smarter mocks
                user_msg = ""
                for msg in request.messages:
                    if msg.get("role") == "user":
                        user_msg += msg.get("content", "") + " "
                user_msg_lower = user_msg.lower()
                
                event_name = "Major News Event"
                if "protest" in user_msg_lower:
                    event_name = "Protest"
                elif "attack" in user_msg_lower:
                    event_name = "Attack"

                for field_name, field_type in schema.model_fields.items():
                    # Generate simple mock values by field type
                    origin = getattr(field_type.annotation, "__origin__", field_type.annotation)
                    if origin is bool:
                        fields[field_name] = True
                    elif origin is float:
                        fields[field_name] = 0.95
                    elif origin is int:
                        fields[field_name] = 42
                    elif origin is list:
                        args = getattr(field_type.annotation, "__args__", None)
                        item_type = args[0] if args else None
                        if item_type and isinstance(item_type, type) and issubclass(item_type, BaseModel):
                            fields[field_name] = []
                        else:
                            fields[field_name] = ["Mock bullet point"]
                    elif origin is str:
                        if field_name == "headline":
                            fields[field_name] = f"[Mock] {event_name}"
                        elif field_name == "category":
                            fields[field_name] = "world"
                        else:
                            fields[field_name] = f"Mock {field_name.replace('_', ' ')}"
                    else:
                        fields[field_name] = None
                parsed = schema.model_validate(fields)
                content = parsed.model_dump_json()
            elif isinstance(request.response_format, dict):
                # Simple fallback JSON dict
                parsed = {"status": "success", "message": "Mock JSON fallback"}
                content = json.dumps(parsed)

        return GatewayResponse(
            content=content,
            parsed=parsed,
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            latency_ms=5.0,
            provider="mock",
            model=request.model,
            key_used="mock-key"
        )

    async def execute(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        return self._generate_mock_output(request)

    def execute_sync(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        return self._generate_mock_output(request)
