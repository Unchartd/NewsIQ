"""Pipeline-level LLM response cache — never call the LLM twice for identical input.

Content-addressed cache keyed by:
    pipeline_stage:model:prompt_version:pipeline_version:temperature:content_hash

Invalidation is content-driven, not time-driven:
    - Article content changes → new content_hash → new key
    - Prompt changes → new prompt_version → new key
    - Pipeline version bump → new pipeline_version → new key
    - Model changes → new model → new key
    - Temperature changes → new temperature → new key

TTL is used only as a Redis memory cleanup mechanism (30 days).

Feature flag: PIPELINE_CACHE_ENABLED (defaults to True)
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# TTL is for Redis memory cleanup only — NOT a correctness mechanism.
# Content-addressed keys guarantee that stale data is never served.
CLEANUP_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


class PipelineCache:
    """Content-addressed LLM response cache backed by Redis.

    Key format:
        ``llm_cache:{stage}:{model}:{prompt_version}:{pipeline_version}:{temperature}:{content_hash}``

    Invalidation is implicit:
        When any key component changes, the new key is different → automatic cache miss.
        Old entries expire via the 30-day cleanup TTL.
    """

    # ── Hashing ────────────────────────────────────────────────────────────────

    @staticmethod
    def content_hash(text: str) -> str:
        """SHA-256 digest of normalized text content."""
        normalized = text.strip().replace("\r\n", "\n").replace("\r", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def composite_hash(*parts: str) -> str:
        """SHA-256 digest of multiple concatenated parts (for multi-input stages)."""
        combined = "::".join(p.strip() for p in parts)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    # ── Key Construction ───────────────────────────────────────────────────────

    @staticmethod
    def cache_key(
        stage: str,
        model: str,
        prompt_version: str,
        content_hash: str,
        temperature: float = 0.0,
    ) -> str:
        """Build a deterministic, content-addressed cache key.

        Every dimension that can affect LLM output is part of the key:
        stage, model, prompt_version, pipeline_version, temperature, content_hash.
        """
        pipeline_version = getattr(settings, "PIPELINE_VERSION", "1.0.0")
        # Normalize temperature to 2 decimal places to avoid float precision issues
        temp_str = f"{temperature:.2f}"
        return f"llm_cache:{stage}:{model}:{prompt_version}:{pipeline_version}:{temp_str}:{content_hash}"

    # ── Cache Operations ───────────────────────────────────────────────────────

    async def get(
        self,
        stage: str,
        model: str,
        prompt_version: str,
        content_hash: str,
        temperature: float = 0.0,
    ) -> dict[str, Any] | None:
        """Return cached LLM response, or None on miss/disabled/error."""
        if not self._is_enabled():
            return None

        key = self.cache_key(stage, model, prompt_version, content_hash, temperature)

        try:
            from app.services.cache_service import cache_service

            raw = await cache_service.get(key)
            if raw is not None:
                self._record_metric(stage, "hit")
                logger.debug("Pipeline cache HIT: %s", key)
                return raw
        except Exception as e:
            self._record_metric(stage, "get_error")
            logger.warning("Pipeline cache GET error for %s: %s", key, e)

        self._record_metric(stage, "miss")
        logger.debug("Pipeline cache MISS: %s", key)
        return None

    async def set(
        self,
        stage: str,
        model: str,
        prompt_version: str,
        content_hash: str,
        response_data: dict[str, Any],
        temperature: float = 0.0,
    ) -> None:
        """Store an LLM response in cache.

        Uses a uniform 30-day TTL for Redis memory cleanup.
        Correctness is guaranteed by the content-addressed key, not TTL.
        """
        if not self._is_enabled():
            return

        key = self.cache_key(stage, model, prompt_version, content_hash, temperature)

        try:
            from app.services.cache_service import cache_service

            await cache_service.set(key, response_data, ttl=CLEANUP_TTL_SECONDS)
            self._record_metric(stage, "set")
            logger.debug("Pipeline cache SET: %s", key)
        except Exception as e:
            self._record_metric(stage, "set_error")
            logger.warning("Pipeline cache SET error for %s: %s", key, e)

    async def invalidate_stage(self, stage: str) -> None:
        """Invalidate all cached responses for a given stage.

        Typically unnecessary with content-addressed keys (changing any
        dimension automatically creates a new key), but useful for
        emergency cache flushes.
        """
        try:
            from app.services.cache_service import cache_service

            await cache_service.delete_pattern(f"llm_cache:{stage}:*")
            await cache_service.delete_pattern(f"stage_cache:{stage}:*")
            logger.info("Invalidated all pipeline cache entries for stage: %s", stage)
        except Exception as e:
            logger.warning("Pipeline cache invalidation error for stage %s: %s", stage, e)

    async def get_stage_result(
        self, stage: str, content_hash: str
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Fetch cached result for a whole pipeline stage based on composite input hash."""
        if not self._is_enabled():
            return None

        pipeline_version = getattr(settings, "PIPELINE_VERSION", "1.0.0")
        key = f"stage_cache:{stage}:{pipeline_version}:{content_hash}"

        try:
            from app.services.cache_service import cache_service

            raw = await cache_service.get(key)
            if raw is not None:
                self._record_metric(stage, "stage_hit")
                logger.debug("Stage-level cache HIT: %s", key)
                return raw
        except Exception as e:
            self._record_metric(stage, "stage_get_error")
            logger.warning("Stage cache GET error for %s: %s", key, e)

        self._record_metric(stage, "stage_miss")
        logger.debug("Stage-level cache MISS: %s", key)
        return None

    async def set_stage_result(self, stage: str, content_hash: str, result_data: Any) -> None:
        """Cache the result of an entire pipeline stage."""
        if not self._is_enabled():
            return

        pipeline_version = getattr(settings, "PIPELINE_VERSION", "1.0.0")
        key = f"stage_cache:{stage}:{pipeline_version}:{content_hash}"

        try:
            from app.services.cache_service import cache_service

            await cache_service.set(key, result_data, ttl=CLEANUP_TTL_SECONDS)
            self._record_metric(stage, "stage_set")
            logger.debug("Stage-level cache SET: %s", key)
        except Exception as e:
            self._record_metric(stage, "stage_set_error")
            logger.warning("Stage cache SET error for %s: %s", key, e)

    # ── Metrics ────────────────────────────────────────────────────────────────

    @staticmethod
    def _record_metric(stage: str, operation: str) -> None:
        """Record a pipeline cache operation in Prometheus."""
        try:
            from app.core.metrics import newsiq_pipeline_cache_operations

            newsiq_pipeline_cache_operations.labels(stage=stage, operation=operation).inc()
        except Exception:
            pass  # Metrics are best-effort

    # ── Feature Flag ───────────────────────────────────────────────────────────

    @staticmethod
    def _is_enabled() -> bool:
        """Check if pipeline caching is enabled via config."""
        return getattr(settings, "PIPELINE_CACHE_ENABLED", True)


# Singleton
pipeline_cache = PipelineCache()
