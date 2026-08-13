import logging
from typing import Any, Literal, TypedDict, cast

from app.core.config import settings

logger = logging.getLogger(__name__)

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
    # ── Bedrock (Mantle) chat models ────────────────────────────────────────
    # These MUST be registered here, not only in CAPABILITY_ROUTING and the
    # prompt manifests. generate_stage() — the path every prompt-driven stage
    # actually takes — resolves manifest model names through MODEL_FALLBACKS,
    # and an unregistered name previously fell through to a default that sent
    # it to Gemini. Production was therefore POSTing
    # "qwen.qwen3-vl-235b-a22b-instruct" to Google and getting 404s on every
    # fallback tier, so the pipeline had no cross-provider redundancy at all
    # while Gemini was rate-limited.
    "qwen.qwen3-vl-235b-a22b-instruct": [
        {
            "provider": "bedrock",
            "model": "qwen.qwen3-vl-235b-a22b-instruct",
            "temperature": 0.1,
            "timeout": 30.0,
        },
    ],
    "deepseek.v3.2": [
        {"provider": "bedrock", "model": "deepseek.v3.2", "temperature": 0.1, "timeout": 30.0},
    ],
    "qwen.qwen3-235b-a22b-2507": [
        {
            "provider": "bedrock",
            "model": "qwen.qwen3-235b-a22b-2507",
            "temperature": 0.1,
            "timeout": 30.0,
        },
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

# Provider and model are two halves of one decision. Setting only one — e.g.
# switching EMBEDDING_MODEL to an OpenRouter model while EMBEDDING_PROVIDER is
# still "gemini" — would POST the model name to the wrong API and 404 every
# embedding, exactly how the Bedrock chat models silently failed for days.
_MODEL_PREFIX_OWNER = {
    "gemini-": "gemini",
    "qwen/": "openrouter",
    "openai/": "openrouter",
    "sentence-transformers/": "openrouter",
    "baai/": "openrouter",
    "mistralai/": "openrouter",
}


def _validate_embedding_config() -> str | None:
    """Return a description of any embedding misconfiguration, else None.

    Deliberately NOT fatal. An earlier version raised at import, which meant a
    single mistyped env var crash-looped every container — API, worker, beat
    and web — and took the whole site down twice. The blast radius of a bad
    embedding setting must be embeddings, not the product.

    ai_gateway.embeddings() refuses with this message, so the failure is loud
    and precise at the point of use while everything else keeps serving.
    """
    if settings.EMBEDDING_PROVIDER not in _VALID_PROVIDERS:
        return (
            f"EMBEDDING_PROVIDER={settings.EMBEDDING_PROVIDER!r} is not one of {_VALID_PROVIDERS}."
        )
    for prefix, owner in _MODEL_PREFIX_OWNER.items():
        if settings.EMBEDDING_MODEL.startswith(prefix) and settings.EMBEDDING_PROVIDER != owner:
            return (
                f"EMBEDDING_MODEL={settings.EMBEDDING_MODEL!r} belongs to provider "
                f"{owner!r}, but EMBEDDING_PROVIDER={settings.EMBEDDING_PROVIDER!r}. "
                "Set both together."
            )
    return None


EMBEDDING_CONFIG_ERROR: str | None = _validate_embedding_config()

if EMBEDDING_CONFIG_ERROR:
    logger.error(
        "Embedding configuration is invalid — embeddings are DISABLED until fixed: %s "
        "Articles will accumulate at embedding_status='pending' and clustering will "
        "not advance. The rest of the application is unaffected.",
        EMBEDDING_CONFIG_ERROR,
    )

# Fall back to a routable provider so module import (and therefore the whole
# app) still succeeds; embeddings themselves are gated by EMBEDDING_CONFIG_ERROR.
_EFFECTIVE_PROVIDER = (
    settings.EMBEDDING_PROVIDER if settings.EMBEDDING_PROVIDER in _VALID_PROVIDERS else "gemini"
)
EMBEDDING_PROVIDER: ProviderType = cast(ProviderType, _EFFECTIVE_PROVIDER)


CAPABILITY_ROUTING: dict[str, CapabilityRoute] = {
    "event_extraction": {
        "primary": {
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
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
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
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
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
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
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
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
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
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
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 45.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
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
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 30.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
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
            "model": "gemini-3.5-flash-lite",
            "temperature": 0.1,
            "timeout": 15.0,
        },
        "fallback": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
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
