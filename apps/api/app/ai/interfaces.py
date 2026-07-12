from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


class APIKey(BaseModel):
    """Representation of an API key inside the provider key pool."""

    key: str = Field(..., description="The raw API key string")
    provider: str = Field(..., description="The provider name (gemini, nvidia, openrouter, etc.)")
    requests_per_minute: int = Field(60, description="Rate limit RPM")
    requests_per_day: int = Field(10000, description="Rate limit RPD")
    cooldown_until: datetime | None = Field(None, description="Cooldown expiration timestamp")
    healthy: bool = Field(True, description="True if key is healthy, False if disabled/failing")

    def is_cooling_down(self) -> bool:
        """Check if this key is currently in cooldown."""
        if self.cooldown_until is None:
            return False
        return datetime.utcnow() < self.cooldown_until

    def get_masked(self) -> str:
        """Return a masked representation of the API key for safe logging."""
        if len(self.key) <= 8:
            return "****"
        return f"{self.key[:4]}...{self.key[-4:]}"


class GatewayRequest(BaseModel):
    """Unified request schema for AI Gateway calls."""

    model: str = Field(..., description="Target model ID")
    messages: list[dict[str, Any]] = Field(..., description="OpenAI-style message list")
    temperature: float = Field(0.0, description="Sampling temperature")
    response_format: dict[str, Any] | type[BaseModel] | None = Field(
        None, description="Output validation schema"
    )
    stage: str = Field("unknown", description="Pipeline stage for tracing")
    story_id: str = Field("", description="Story ID context for tracing")
    article_id: str = Field("", description="Article ID context for tracing")
    timeout: float = Field(30.0, description="Provider timeout")

    class Config:
        arbitrary_types_allowed = True


class GatewayResponse(BaseModel):
    """Unified response schema for AI Gateway calls."""

    content: str = Field(..., description="Raw text response content")
    parsed: Any | None = Field(
        None, description="Parsed structured response matching response_format"
    )
    input_tokens: int = Field(0, description="Count of input prompt tokens")
    output_tokens: int = Field(0, description="Count of output completion tokens")
    total_tokens: int = Field(0, description="Total token count")
    latency_ms: float = Field(0.0, description="Call duration in milliseconds")
    cost_usd: float = Field(0.0, description="Computed cost of the call in USD")
    provider: str = Field(..., description="The model provider that fulfilled the call")
    model: str = Field(..., description="The specific model used")
    key_used: str | None = Field(None, description="Masked version of the API key used")
    error: str | None = Field(None, description="Error message if the call failed")


class HealthStatus(BaseModel):
    """Result of a provider health check."""

    healthy: bool
    latency_ms: float
    supported_models: list[str]
    error: str | None = None


class AIProvider(Protocol):
    """Unified AI Provider interface."""

    async def generate(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        """Asynchronously execute the request and validate its schema."""
        ...

    def stream(self, request: GatewayRequest, api_key: APIKey) -> AsyncGenerator[str, None]:
        """Asynchronously stream raw completion content."""
        ...

    async def health(self, api_key: APIKey) -> HealthStatus:
        """Verify API key authentication, model accessibility, and response latency."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens locally or via provider APIs."""
        ...

    async def embeddings(self, text: str, api_key: APIKey, model: str | None = None) -> list[float]:
        """Generate vector embedding."""
        ...
