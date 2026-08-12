from typing import Any, Literal, TypedDict, cast

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
    ],
    "gemini-embedding-2": [
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
    # ── Embedding model chains ──────────────────────────────────────────────
    # SINGLE-MODEL ONLY. These chains previously fell back mpnet -> qwen3 ->
    # gemini, i.e. across three mutually incomparable vector spaces. Measured:
    # the same sentence scores cosine 0.02 across two of them, while different
    # paraphrases within one model score 0.84-0.92 (Stage B matches at ~0.67).
    # Retrying the SAME model is redundancy; switching models is corruption.
    "sentence-transformers/all-mpnet-base-v2": [
        {
            "provider": "openrouter",
            "model": "sentence-transformers/all-mpnet-base-v2",
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
    ],
    "openai/text-embedding-3-small": [
        {
            "provider": "openrouter",
            "model": "openai/text-embedding-3-small",
            "temperature": 0.0,
            "timeout": 15.0,
        },
    ],
    # baai/bge-m3 and mistralai/mistral-embed are deliberately absent: they emit
    # 1024 dims and ignore the `dimensions` parameter (verified live), so they
    # cannot serve this pipeline without invalid truncation.
}


# Capability-based routing configuration — strictly gemini-3.1-flash-lite & gemini-3.5-flash-lite
_VALID_PROVIDERS: tuple[str, ...] = ("nvidia", "gemini", "openrouter", "mock", "bedrock")

if settings.EMBEDDING_PROVIDER not in _VALID_PROVIDERS:
    raise ValueError(
        f"EMBEDDING_PROVIDER={settings.EMBEDDING_PROVIDER!r} is not one of {_VALID_PROVIDERS}. "
        "Failing at import: an unroutable embedding provider would surface later as "
        "every article silently failing to embed."
    )
# Validated above, so the cast is safe and mypy gets the Literal it needs.
EMBEDDING_PROVIDER: ProviderType = cast(ProviderType, settings.EMBEDDING_PROVIDER)


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
    # ALL THREE TIERS MUST NAME THE SAME MODEL.
    #
    # Unlike chat, embeddings are not interchangeable across models: every
    # article vector shares one Qdrant collection and is compared by cosine
    # similarity. Measured on candidate models, the SAME sentence embedded by
    # all-mpnet-base-v2 vs qwen3-embedding-8b scores cosine 0.02, while two
    # DIFFERENT paraphrases within one model score 0.84-0.92 — Stage B matches
    # at ~0.67. A cross-model "fallback" therefore yields articles that can
    # never cluster, and looks exactly like success.
    #
    # ai_gateway.embeddings() skips any tier naming a different model, and
    # test_embedding_space_integrity.py fails the build if these diverge. The
    # tiers exist for retry across providers/keys serving the SAME model.
    #
    # Changing settings.EMBEDDING_MODEL invalidates the entire existing corpus
    # and requires a re-embed — see app/scripts/reembed_corpus.py.
    "embedding": {
        "primary": {
            "provider": EMBEDDING_PROVIDER,
            "model": settings.EMBEDDING_MODEL,
            "temperature": 0.0,
            "timeout": 15.0,
        },
        "fallback": {
            "provider": EMBEDDING_PROVIDER,
            "model": settings.EMBEDDING_MODEL,
            "temperature": 0.0,
            "timeout": 15.0,
        },
        "lastFallback": {
            "provider": EMBEDDING_PROVIDER,
            "model": settings.EMBEDDING_MODEL,
            "temperature": 0.0,
            "timeout": 15.0,
        },
    },
}
