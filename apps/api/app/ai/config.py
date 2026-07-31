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


# Model fallback chains — configured strictly for Gemini API (15 RPM / 500 RPD for Flash, 100 RPM / 1500 RPD for Embeddings)
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    ],
    "gemini-2.5-flash": [
        {"provider": "gemini", "model": "gemini-2.5-flash", "temperature": 0.1, "timeout": 30.0},
        {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    ],
    "gemini-2.5-pro": [
        {"provider": "gemini", "model": "gemini-2.5-pro", "temperature": 0.1, "timeout": 45.0},
        {"provider": "gemini", "model": "gemini-2.5-flash", "temperature": 0.1, "timeout": 30.0},
        {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    ],
    "gemini-2.5-flash-lite": [
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
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
    "gemini-embedding-001": [
        {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        {
            "provider": "gemini",
            "model": "text-embedding-004",
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
    "text-embedding-004": [
        {
            "provider": "gemini",
            "model": "text-embedding-004",
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
            "model": "text-embedding-004",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    ],
    "mock": [
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
}


# Capability-based routing configuration — All pipeline capabilities strictly mapped to Gemini API
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 45.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
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
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "timeout": 15.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
            "temperature": 0.1,
            "timeout": 15.0,
        },
    },
    # ── Embedding Capability ──────────────────────────────────────────────────
    "embedding": {
        "primary": {
            "provider": "gemini",
            "model": settings.EMBEDDING_MODEL or "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "text-embedding-004",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        "lastFallback": {
            "provider": "gemini",
            "model": "gemini-embedding-001",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    },
}
