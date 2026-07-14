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


# Model fallback chains (configuration-driven instead of hardcoded)
# Scoped strictly to Gemini, AWS Bedrock, NVIDIA NIM, and OpenRouter.
MODEL_FALLBACKS: dict[str, list[dict[str, Any]]] = {
    "gemini-3.1-flash-lite": [
        {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
    "gemini-2.5-flash": [
        {"provider": "gemini", "model": "gemini-2.5-flash", "temperature": 0.1, "timeout": 30.0},
        {
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
    "gemini-2.5-pro": [
        {"provider": "gemini", "model": "gemini-2.5-pro", "temperature": 0.1, "timeout": 45.0},
        {
            "provider": "bedrock",
            "model": "deepseek.v3.2",
            "temperature": 0.1,
            "timeout": 45.0,
        },
        {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-pro",
            "temperature": 0.1,
            "timeout": 45.0,
        },
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
    "gemini-2.5-flash-lite": [
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
    "deepseek-ai/deepseek-v4-flash": [
        {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
    "deepseek-ai/deepseek-v4-pro": [
        {"provider": "gemini", "model": "gemini-2.5-pro", "temperature": 0.1, "timeout": 45.0},
        {
            "provider": "bedrock",
            "model": "deepseek.v3.2",
            "temperature": 0.1,
            "timeout": 45.0,
        },
        {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-pro",
            "temperature": 0.1,
            "timeout": 45.0,
        },
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
    "mock": [
        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
    ],
}


# Capability-based routing configuration
# fallback tree: first gemini then amazon bedrock, then Nvidia
CAPABILITY_ROUTING: dict[str, CapabilityRoute] = {
    "event_extraction": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
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
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
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
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    # ── Pro Capabilities ────────────────────────────────────────────────────
    "source_comparison": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "bedrock",
            "model": "deepseek.v3.2",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-pro",
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
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    # summary_generation: called by ai_service.summarize_story_from_kg() — routes to Pro for quality
    "summary_generation": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "temperature": 0.1,
            "timeout": 60.0,
        },
        "fallback": {
            "provider": "bedrock",
            "model": "deepseek.v3.2",
            "temperature": 0.1,
            "timeout": 60.0,
        },
        "lastFallback": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-pro",
            "temperature": 0.1,
            "timeout": 60.0,
        },
    },
    # contradiction_detection: alias of contradiction_analysis — used by agent fallback path
    "contradiction_detection": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "lastFallback": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    },
    # entity_linking: used by entity_linker._disambiguate_with_llm()
    "entity_linking": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "temperature": 0.1,
            "timeout": 15.0,
        },
        "fallback": {
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 15.0,
        },
        "lastFallback": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "temperature": 0.1,
            "timeout": 15.0,
        },
    },
    # ── Embedding ───────────────────────────────────────────────────────────
    "embedding": {
        "primary": {
            "provider": "gemini",
            "model": settings.EMBEDDING_MODEL,
            "temperature": 0.0,
            "timeout": 15.0,
        },
        "fallback": {
            "provider": "nvidia",
            "model": "nvidia/llama-3.2-nv-embedqa-4b-v1",
            "temperature": 0.0,
            "timeout": 15.0,
        },
        "lastFallback": {
            "provider": "openrouter",
            "model": "nomic/nomic-embed-text-v1.5",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    },
}
