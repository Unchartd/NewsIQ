"""Per-model circuit breaking for quota-exhausted LLMs.

The gateway's fallback chain is per-model, and each model expands into its own
sub-chain of up to three entries, each retried three times. For a stage whose
preferred model is gemini-3.5-flash-lite that means nine Gemini calls — with
exponential backoff between them — before a non-Gemini fallback is ever tried.

That is correct for a transient 429 and useless for an exhausted daily quota,
which cannot recover within seconds. Measured over twenty minutes with both
Gemini models past their free-tier limit: 540 Gemini attempts against 5 Bedrock,
while every Gemini call returned RESOURCE_EXHAUSTED.

Health is tracked per MODEL rather than per provider because quotas are
per-model: gemini-3.5-flash-lite being exhausted says nothing about
gemini-3.1-flash-lite, and tripping the whole provider would strand both.
"""

from __future__ import annotations

import logging
import re

from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

_KEY = "ai:model_exhausted:{model}"

# A plain 429 may clear in seconds; a spent daily allowance will not. Both are
# reported as RateLimitError, so the message decides how long to stay off.
_TRANSIENT_COOLDOWN_SECONDS = 120
_QUOTA_COOLDOWN_SECONDS = 3600

_DAILY_QUOTA_MARKERS = (
    "resource_exhausted",
    "perday",
    "per day",
    "daily",
    "free_tier",
    "quota exceeded",
    "insufficient",
)

_RETRY_DELAY_RE = re.compile(r"retry in (\d+(?:\.\d+)?)s", re.IGNORECASE)


def cooldown_for(error_text: str) -> int:
    """How long to disable a model after *error_text*.

    Prefers the provider's own retryDelay when it offers one and it is longer
    than the transient default, so we neither hammer nor over-penalise.
    """
    lowered = error_text.lower()
    if any(marker in lowered for marker in _DAILY_QUOTA_MARKERS):
        return _QUOTA_COOLDOWN_SECONDS

    match = _RETRY_DELAY_RE.search(error_text)
    if match:
        try:
            return max(int(float(match.group(1))) + 1, _TRANSIENT_COOLDOWN_SECONDS)
        except ValueError:
            pass
    return _TRANSIENT_COOLDOWN_SECONDS


async def is_exhausted(model: str) -> bool:
    """True when *model* is known to be rate-limited and should be skipped."""
    redis_client = cache_service._redis
    if not redis_client or not model:
        return False
    try:
        return bool(await redis_client.get(_KEY.format(model=model)))
    except Exception as exc:  # a cache problem must never block generation
        logger.debug("Model health lookup failed for %s: %s", model, exc, exc_info=True)
        return False


async def mark_exhausted(model: str, error_text: str) -> int:
    """Disable *model* for a cooldown derived from the error. Returns the TTL."""
    ttl = cooldown_for(error_text)
    redis_client = cache_service._redis
    if not redis_client or not model:
        return ttl
    try:
        await redis_client.set(_KEY.format(model=model), "1", ex=ttl)
        logger.warning("Model %s is rate-limited; skipping it for %ds.", model, ttl)
        from app.core.metrics import newsiq_ai_model_circuit_open_total

        newsiq_ai_model_circuit_open_total.labels(model=model).inc()
    except Exception as exc:
        logger.debug("Could not record model exhaustion for %s: %s", model, exc, exc_info=True)
    return ttl


async def filter_healthy(models: list[str]) -> list[str]:
    """Drop exhausted models, unless every one is exhausted.

    Returning an empty list would turn a slow call into a failed one, so when
    nothing is healthy the original order is preserved and the caller tries
    anyway — a long shot beats no shot.
    """
    healthy = [m for m in models if not await is_exhausted(m)]
    if not healthy:
        logger.warning("Every candidate model is rate-limited (%s); trying anyway.", models)
        return models
    return healthy
