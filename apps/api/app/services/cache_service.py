"""Redis caching service for hot stories, trending feeds, and search results.

Implements the cache key scheme documented in the Backend Schema Document:
  story:{storyId}        TTL 15 minutes
  trending:{scope}       TTL 5 minutes
  search:{hash}          TTL 30 minutes

All operations fail open: if Redis is unavailable, cache reads return None
and writes are silently skipped so the API keeps serving from PostgreSQL.

TLS / Upstash support:
  When REDIS_URL starts with "rediss://", the client connects over TLS with
  ssl_cert_reqs disabled (Upstash manages its own certificate).

Migration to self-hosted Redis:
  Change REDIS_URL to your Redis host (redis://). No code changes needed.
"""

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# TTLs in seconds
TTL_STORY = 15 * 60
TTL_TRENDING = 5 * 60
TTL_SEARCH = 30 * 60


def _make_redis_client(url: str) -> aioredis.Redis | None:
    """Create an async Redis client with automatic TLS detection.

    Handles both:
      redis://host:port   → plain TCP
      rediss://host:port  → TLS (Upstash, Redis Cloud, etc.)
    """
    if not url:
        return None
    try:
        kwargs: dict = {"decode_responses": True}
        if url.startswith("rediss://"):
            import ssl

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs["ssl_context"] = ctx
        return aioredis.from_url(url, **kwargs)
    except Exception as e:
        logger.error("Failed to create Redis client for %s: %s", url.split("@")[-1], e)
        return None


class CacheService:
    """Thin async Redis wrapper with JSON serialization and fail-open semantics."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = _make_redis_client(settings.REDIS_URL)
        if self._redis is None:
            logger.warning("CacheService: Redis client not initialized. Caching disabled.")

    async def get(self, key: str) -> Any | None:
        """Return the cached JSON value for a key, or None on miss/error."""
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception as e:
            logger.warning("Cache GET failed for %s: %s", key, e)
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Store a JSON-serializable value with a TTL. Silently skips on error."""
        if not self._redis:
            return
        try:
            await self._redis.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception as e:
            logger.warning("Cache SET failed for %s: %s", key, e)

    async def delete(self, *keys: str) -> None:
        """Delete one or more keys. Silently skips on error."""
        if not self._redis or not keys:
            return
        try:
            await self._redis.delete(*keys)
        except Exception as e:
            logger.warning("Cache DELETE failed for %s: %s", keys, e)

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a glob pattern (e.g. 'trending:*')."""
        if not self._redis:
            return
        try:
            async for key in self._redis.scan_iter(match=pattern):
                await self._redis.delete(key)
        except Exception as e:
            logger.warning("Cache DELETE pattern failed for %s: %s", pattern, e)

    async def ping(self) -> bool:
        """Return True if Redis is reachable. Used for health checks."""
        if not self._redis:
            return False
        try:
            return await self._redis.ping()
        except Exception as e:
            logger.exception("Redis ping failed:")
            return False

    # ─────────────────────────────────────────────
    # Key builders
    # ─────────────────────────────────────────────
    @staticmethod
    def story_key(story_id: str) -> str:
        return f"story:{story_id}"

    @staticmethod
    def trending_key(scope: str = "global") -> str:
        return f"trending:{scope}"

    @staticmethod
    def search_key(query: str, category: str | None, limit: int, offset: int) -> str:
        raw = f"{query}|{category or ''}|{limit}|{offset}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"search:{digest}"

    async def invalidate_story(self, story_id: str) -> None:
        """Invalidate a story and all trending/search caches affected by it."""
        await self.delete(self.story_key(story_id))
        await self.delete_pattern("trending:*")
        await self.delete_pattern("search:*")


cache_service = CacheService()
