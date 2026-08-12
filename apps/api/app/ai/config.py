from typing import Any, Literal, TypedDict

from app.core.config import settings

ProviderType = Literal["nvidia", "gemini", "openrouter", "mock", "bedrock"]


class ProviderModelRoute(TypedDict):
    provider: ProviderType
    model: str
    temperature: float
    timeout: float


class CapabilityRoute(TypedDict):
    primary: ProviderModelRoute
    fallback: ProviderModelRoute
    lastFallback: ProviderModelRoute


# Model fallback chains — configured strictly for Gemini API (gemini-3.1-flash-lite & gemini-3.5-flash-lite)
MODEL_FALLBACKS: dict[str, list[dict[str, Any]]] = {
    "gemini-3.1-flash-lite": [
        {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    ],
    "gemini-3.5-flash-lite": [
        {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    ],
    "gemini-embedding-001": [
        {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-embedding-2",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    ],
    "gemini-embedding-2": [
        {
            "provider": "gemini",
            "model": "gemini-embedding-2",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-embedding-2",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    ],
    "mock": [
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
    # ── OpenRouter embedding model chains ────────────────────────────────────
    # Each model falls back to the cheapest native-768 model then to Gemini.
    "sentence-transformers/all-mpnet-base-v2": [
        {
            "provider": "openrouter",
            "model": "sentence-transformers/all-mpnet-base-v2",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "openrouter",
            "model": "qwen/qwen3-embedding-8b",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    ],
    "qwen/qwen3-embedding-8b": [
        {
            "provider": "openrouter",
            "model": "qwen/qwen3-embedding-8b",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "openrouter",
            "model": "sentence-transformers/all-mpnet-base-v2",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    ],
    "baai/bge-m3": [
        {
            "provider": "openrouter",
            "model": "baai/bge-m3",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "openrouter",
            "model": "sentence-transformers/all-mpnet-base-v2",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    ],
    "openai/text-embedding-3-small": [
        {
            "provider": "openrouter",
            "model": "openai/text-embedding-3-small",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "openrouter",
            "model": "sentence-transformers/all-mpnet-base-v2",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    ],
}


# Capability-based routing configuration — strictly gemini-3.1-flash-lite & gemini-3.5-flash-lite
CAPABILITY_ROUTING: dict[str, CapabilityRoute] = {
    "event_extraction": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            # Cross-provider tier: when Gemini quota is exhausted, every
            # all-Gemini chain fails as one. Bedrock (OpenAI-compatible
            # Mantle endpoint) gives this capability a genuinely
            # independent failure domain.
            "provider": "bedrock",
            "model": settings.AWS_BEDROCK_CHAT_MODEL,
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    "entity_extraction": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            # Cross-provider tier: when Gemini quota is exhausted, every
            # all-Gemini chain fails as one. Bedrock (OpenAI-compatible
            # Mantle endpoint) gives this capability a genuinely
            # independent failure domain.
            "provider": "bedrock",
            "model": settings.AWS_BEDROCK_CHAT_MODEL,
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    "cluster_verification": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            # Cross-provider tier: when Gemini quota is exhausted, every
            # all-Gemini chain fails as one. Bedrock (OpenAI-compatible
            # Mantle endpoint) gives this capability a genuinely
            # independent failure domain.
            "provider": "bedrock",
            "model": settings.AWS_BEDROCK_CHAT_MODEL,
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    "source_comparison": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            # Cross-provider tier: when Gemini quota is exhausted, every
            # all-Gemini chain fails as one. Bedrock (OpenAI-compatible
            # Mantle endpoint) gives this capability a genuinely
            # independent failure domain.
            "provider": "bedrock",
            "model": settings.AWS_BEDROCK_CHAT_MODEL,
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    "summary_reflection": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            # Cross-provider tier: when Gemini quota is exhausted, every
            # all-Gemini chain fails as one. Bedrock (OpenAI-compatible
            # Mantle endpoint) gives this capability a genuinely
            # independent failure domain.
            "provider": "bedrock",
            "model": settings.AWS_BEDROCK_CHAT_MODEL,
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    "summary_generation": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 45.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 45.0,
        },
        "lastFallback": {
            # Cross-provider tier: when Gemini quota is exhausted, every
            # all-Gemini chain fails as one. Bedrock (OpenAI-compatible
            # Mantle endpoint) gives this capability a genuinely
            # independent failure domain.
            "provider": "bedrock",
            "model": settings.AWS_BEDROCK_CHAT_MODEL,
            "temperature": 0.1,
            "timeout": 45.0,
        },
    },
    "contradiction_detection": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            # Cross-provider tier: when Gemini quota is exhausted, every
            # all-Gemini chain fails as one. Bedrock (OpenAI-compatible
            # Mantle endpoint) gives this capability a genuinely
            # independent failure domain.
            "provider": "bedrock",
            "model": settings.AWS_BEDROCK_CHAT_MODEL,
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    "entity_linking": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 15.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 15.0,
        },
        "lastFallback": {
            # Cross-provider tier: when Gemini quota is exhausted, every
            # all-Gemini chain fails as one. Bedrock (OpenAI-compatible
            # Mantle endpoint) gives this capability a genuinely
            # independent failure domain.
            "provider": "bedrock",
            "model": settings.AWS_BEDROCK_CHAT_MODEL,
            "temperature": 0.1,
            "timeout": 15.0,
        },
    },
    # ── Embedding Capability ──────────────────────────────────────────────────
    # Primary and first fallback run on OpenRouter (cost-optimised, native-768
    # or variable-dim models). Gemini is kept as an emergency last-resort so
    # the vector space stays consistent if OpenRouter is unreachable.
    "embedding": {
        "primary": {
            # $0.005/M — native 768-dim, no truncation required
            "provider": "openrouter",
            "model": "sentence-transformers/all-mpnet-base-v2",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        "fallback": {
            # $0.01/M — best multilingual quality, supports dimensions param
            "provider": "openrouter",
            "model": "qwen/qwen3-embedding-8b",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        "lastFallback": {
            # Emergency safety-net — independent failure domain from OpenRouter
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    },
}
