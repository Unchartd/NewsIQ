import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel

from app.ai.interfaces import AIProvider, APIKey, GatewayRequest, GatewayResponse, HealthStatus

logger = logging.getLogger(__name__)


class MockProvider(AIProvider):
    """Mock Provider yielding deterministic text or structured content based on request."""

    def _generate_mock_model_fields(self, schema: type[BaseModel]) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        for field_name, field_type in schema.model_fields.items():
            annotation = field_type.annotation
            origin = getattr(annotation, "__origin__", annotation)

            # Basic type detection
            if origin is bool:
                fields[field_name] = True
            elif origin is float:
                fields[field_name] = 0.95
            elif origin is int:
                fields[field_name] = 42
            elif origin is list:
                args = getattr(annotation, "__args__", None)
                item_type = args[0] if args else None
                if item_type and isinstance(item_type, type) and issubclass(item_type, BaseModel):
                    fields[field_name] = [self._generate_mock_model_fields(item_type)]
                else:
                    fields[field_name] = ["Mock bullet point"]
            elif origin is dict:
                fields[field_name] = {"mock_key": "mock_value"}
            elif origin is str:
                if field_name == "headline":
                    fields[field_name] = "[Mock] News Headline"
                elif field_name == "category":
                    fields[field_name] = "world"
                else:
                    fields[field_name] = f"Mock {field_name.replace('_', ' ')}"
            elif isinstance(origin, type) and issubclass(origin, BaseModel):
                fields[field_name] = self._generate_mock_model_fields(origin)
            else:
                fields[field_name] = None
        return fields

    def _generate_mock_output(self, request: GatewayRequest) -> GatewayResponse:
        content = "Mock response content."
        parsed: Any = None

        # Build schema-based output if response_format is provided
        schema = None
        if request.response_format and isinstance(request.response_format, type) and issubclass(
            request.response_format, BaseModel
        ):
            schema = request.response_format

        if schema:
            try:
                # Custom mock structures per stage/class name
                name_lower = schema.__name__.lower()
                if "verification" in name_lower or "verify" in name_lower:
                    fields = {
                        "verified": True,
                        "confidence": 1.0,
                        "reasoning": "Articles report on the same core news event and share matching details.",
                    }
                elif "extraction" in name_lower or "entity" in name_lower:
                    fields = {
                        "entities": [
                            {"value": "Mock entity", "type": "ORG", "canonical_name": "Mock entity", "confidence": 0.95}
                        ]
                    }
                elif "event" in name_lower:
                    fields = {
                        "primary_event": {
                            "event_type": "POLICY",
                            "actors": ["Officials"],
                            "targets": ["Public interest"],
                            "objects": [],
                            "location": "United States",
                            "event_time": None,
                            "numbers": {},
                            "confidence": 0.95,
                        },
                        "secondary_events": [],
                    }
                elif "comparison" in name_lower:
                    fields = {
                        "focus_area": "General reporting of event details by publisher.",
                        "unique_information": "",
                        "missing_information": "",
                        "contradictions": "",
                    }
                elif "contradiction" in name_lower:
                    fields = {"is_contradiction": False, "description": "", "confidence": 0.0}
                elif "summary" in name_lower:
                    fields = {
                        "headline": "[Mock] News Headline",
                        "one_line_summary": "Reports detail developments regarding mock event.",
                        "short_summary": "Recent media coverage highlights key developments surrounding the mock event.",
                        "detailed_summary": "A synthesis of recent news coverage reveals details regarding the mock event.",
                        "key_facts": ["Mock fact 1", "Mock fact 2"],
                        "category": "world",
                    }
                else:
                    fields = self._generate_mock_model_fields(schema)

                parsed = schema.model_validate(fields)
                content = parsed.model_dump_json()
            except Exception as e:
                logger.error("Failed to generate mock fields for schema %s: %s", schema, e)
                parsed = {"status": "success", "message": "Mock JSON fallback"}
                content = json.dumps(parsed)

        elif request.response_format:
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
            key_used="mock-key",
            cost_usd=0.0,
            error=None,
        )

    async def generate(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        return self._generate_mock_output(request)

    async def stream(self, request: GatewayRequest, api_key: APIKey) -> AsyncGenerator[str, None]:
        response = self._generate_mock_output(request)
        yield response.content

    async def health(self, api_key: APIKey) -> HealthStatus:
        return HealthStatus(
            healthy=True,
            latency_ms=1.0,
            supported_models=["mock"]
        )

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    async def embeddings(self, text: str, api_key: APIKey) -> list[float]:
        # Return a deterministic mock embedding of length 768
        import hashlib

        import numpy as np
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:4], byteorder="big")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(768)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()
