import hashlib
import logging
from typing import Any
from app.core.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

DEFAULT_TTL = 30 * 24 * 60 * 60  # 30 days


class AIGatewayCache:
    """Redis-backed exact response caching for the AI Gateway."""

    @staticmethod
    def _compute_hash(prompt_text: str) -> str:
        """SHA-256 digest of normalized prompt text."""
        normalized = prompt_text.strip().replace("\r\n", "\n").replace("\r", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _cache_key(
        self,
        capability: str,
        model: str,
        prompt_version: str,
        prompt_hash: str,
        temperature: float,
    ) -> str:
        """Construct a deterministic cache key."""
        pipeline_version = getattr(settings, "PIPELINE_VERSION", "1.0.0")
        temp_str = f"{temperature:.2f}"
        return f"ai_cache:{capability}:{model}:{prompt_version}:{pipeline_version}:{temp_str}:{prompt_hash}"

    async def get(
        self,
        capability: str,
        model: str,
        prompt_version: str,
        prompt_text: str,
        temperature: float = 0.0,
    ) -> dict[str, Any] | None:
        """Check the cache for a prior matching request."""
        if not getattr(settings, "PIPELINE_CACHE_ENABLED", True):
            return None

        prompt_hash = self._compute_hash(prompt_text)
        key = self._cache_key(capability, model, prompt_version, prompt_hash, temperature)

        try:
            raw = await cache_service.get(key)
            if raw is not None:
                logger.debug("AI Gateway cache HIT for key: %s", key)
                return raw
        except Exception as e:
            logger.warning("AI Gateway cache GET error for %s: %s", key, e)

        logger.debug("AI Gateway cache MISS for key: %s", key)
        return None

    async def set(
        self,
        capability: str,
        model: str,
        prompt_version: str,
        prompt_text: str,
        response_data: dict[str, Any],
        temperature: float = 0.0,
        ttl: int | None = None,
    ) -> None:
        """Store the response data in the cache."""
        if not getattr(settings, "PIPELINE_CACHE_ENABLED", True):
            return

        prompt_hash = self._compute_hash(prompt_text)
        key = self._cache_key(capability, model, prompt_version, prompt_hash, temperature)
        ttl = ttl if ttl is not None else DEFAULT_TTL

        try:
            await cache_service.set(key, response_data, ttl=ttl)
            logger.debug("AI Gateway cache SET for key: %s", key)
        except Exception as e:
            logger.warning("AI Gateway cache SET error for %s: %s", key, e)


# Singleton
ai_cache = AIGatewayCache()
