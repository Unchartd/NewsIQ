import abc
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel, Field

class GatewayRequest(BaseModel):
    """Unified request schema for LLM Gateway calls."""
    model: str = Field(..., description="Target model ID (e.g., gemini-2.5-flash-lite, gpt-4o-mini)")
    messages: List[Dict[str, Any]] = Field(..., description="OpenAI-style message list: [{'role': 'user/system/assistant', 'content': '...'}]")
    temperature: float = Field(0.0, description="Sampling temperature")
    response_format: Optional[Union[Dict[str, Any], Type[BaseModel]]] = Field(None, description="Pydantic class or JSON schema for structured outputs")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="List of available tools/functions")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Tool choice constraint")
    stage: str = Field("unknown", description="Pipeline stage (e.g. cluster_verification, summary_reflection)")
    story_id: str = Field("", description="Story ID context for tracing")
    article_id: str = Field("", description="Article ID context for tracing")

    class Config:
        arbitrary_types_allowed = True

class GatewayResponse(BaseModel):
    """Unified response schema for LLM Gateway outcomes."""
    content: str = Field(..., description="Raw text response content")
    parsed: Optional[Any] = Field(None, description="Parsed structured response matching response_format")
    input_tokens: int = Field(0, description="Count of input prompt tokens")
    output_tokens: int = Field(0, description="Count of output completion tokens")
    total_tokens: int = Field(0, description="Total token count")
    latency_ms: float = Field(0.0, description="Call duration in milliseconds")
    cost_usd: float = Field(0.0, description="Computed cost of the call in USD")
    provider: str = Field(..., description="The model provider that fulfilled the call (e.g., google, openai, groq)")
    model: str = Field(..., description="The specific model used")
    key_used: Optional[str] = Field(None, description="Masked/hashed version of the API key used")
    error: Optional[str] = Field(None, description="Error message if the call failed")

class APIKey(BaseModel):
    """Representation of an API key inside the provider key pool."""
    key: str = Field(..., description="The raw API key string")
    provider: str = Field(..., description="The provider name (google, openai, groq, etc.)")
    requests_per_minute: int = Field(60, description="Rate limit RPM")
    requests_per_day: int = Field(10000, description="Rate limit RPD")
    cooldown_until: Optional[datetime] = Field(None, description="Cooldown expiration timestamp")
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

class BaseLLMProvider(abc.ABC):
    """Abstract base class representing an LLM client provider."""

    @abc.abstractmethod
    async def execute(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        """Asynchronously execute the LLM request using the given key."""
        pass

    @abc.abstractmethod
    def execute_sync(self, request: GatewayRequest, api_key: APIKey) -> GatewayResponse:
        """Synchronously execute the LLM request using the given key."""
        pass
