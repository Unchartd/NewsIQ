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

import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Any, cast

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_UNSET = object()

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
        kwargs: dict = {
            "decode_responses": True,
            "max_connections": settings.REDIS_MAX_CONNECTIONS,
        }
        if url.startswith("rediss://"):
            kwargs["ssl_check_hostname"] = False
            kwargs["ssl_cert_reqs"] = "none"
        return aioredis.from_url(url, **kwargs)
    except Exception as e:
        logger.error("Failed to create Redis client for %s: %s", url.split("@")[-1], e)
        return None


@asynccontextmanager
async def redis_client(url: str | None = None) -> AsyncIterator[aioredis.Redis | None]:
    """Yield a short-lived Redis client that is always closed.

    Use this for one-off Redis work outside CacheService (broker queries,
    stream publishing, SSE feeds). The plain `aioredis.from_url(...)` /
    `await r.aclose()` pattern leaks the connection whenever the body raises —
    and under Redis pressure the body raises constantly, so the leak
    accelerates exactly when it hurts most.

    Yields None if no URL is configured; callers must handle that.
    """
    client: aioredis.Redis | None = None
    try:
        client = _make_redis_client(url or settings.REDIS_URL)
        yield client
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception as e:
                logger.debug("Failed to close short-lived Redis client: %s", e)


async def redis_llen(client: aioredis.Redis | None, key: str) -> int:
    """Return the length of a Redis list, or 0 when the client is unavailable.

    redis-py types list commands as returning `Awaitable[T] | T` because the
    same class backs its sync and async APIs. Awaiting that union directly is a
    type error, so the cast is centralised here rather than repeated at every
    queue-depth call site.
    """
    if client is None:
        return 0
    return int(await cast("Awaitable[int]", client.llen(key)))


class CacheService:
    """Thin async Redis wrapper with JSON serialization and fail-open semantics.

    Connection lifecycle — read this before changing `_clients`:
      redis-py's asyncio connections are bound to the event loop that created
      them, so a client cannot be shared across loops. Celery's run_async()
      creates a fresh loop per task invocation, so each task needs its own
      client. That makes it the *caller's* responsibility to release the
      client before the loop closes — otherwise every task strands a live
      connection pool and Redis eventually rejects all new connections with
      "ERR max number of clients reached", which trips the pipeline-paused
      fail-safe and silently halts every AI task.

      Call `await cache_service.close_current_loop()` before closing a loop.
      run_async() (app/workers/tasks.py) and the FastAPI lifespan shutdown
      both do this.

      Entries are keyed by id(loop) and store the loop itself, because CPython
      recycles object addresses: a new loop can land on a freed loop's id and
      would otherwise be handed a client bound to the dead loop.
    """

    def __init__(self) -> None:
        self._clients: dict[int, tuple[asyncio.AbstractEventLoop, aioredis.Redis | None]] = {}
        # Test override hook; mirrors VectorService.client. _UNSET (not None) means
        # "no override", so tests can legitimately force _redis to None.
        self._override: Any = _UNSET

    @property
    def _redis(self) -> aioredis.Redis | None:
        if self._override is not _UNSET:
            return self._override
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return None

        loop_id = id(loop)
        entry = self._clients.get(loop_id)
        if entry is not None:
            cached_loop, cached_client = entry
            if cached_loop is loop:
                return cached_client
            # id() collision: a previous loop was freed and this one reused its
            # address. Drop the stale entry rather than returning a dead client.
            logger.debug("CacheService: discarding stale client for reused loop id %d.", loop_id)
            self._clients.pop(loop_id, None)

        client = _make_redis_client(settings.REDIS_URL)
        self._clients[loop_id] = (loop, client)
        if client is None:
            logger.warning(
                "CacheService: Redis client not initialized for loop %d. Caching disabled.",
                loop_id,
            )
        return client

    @_redis.setter
    def _redis(self, value: aioredis.Redis | None) -> None:
        """Override the client (tests only)."""
        self._override = value

    @_redis.deleter
    def _redis(self) -> None:
        """Clear the test override and resume normal per-loop resolution."""
        self._override = _UNSET

    async def close_current_loop(self) -> None:
        """Close and forget the Redis client bound to the running event loop.

        Must be awaited *inside* the loop being torn down. Safe to call when no
        client exists. Never raises — teardown must not fail a task.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        entry = self._clients.pop(id(loop), None)
        if entry is None:
            return
        _, client = entry
        if client is None:
            return
        try:
            await client.aclose()
        except Exception as e:
            logger.debug("CacheService: error closing Redis client: %s", e)

    async def close(self) -> None:
        """Close every known client. Used by application shutdown."""
        for _, client in list(self._clients.values()):
            if client is None:
                continue
            try:
                await client.aclose()
            except Exception as e:
                logger.debug("CacheService: error closing Redis client: %s", e)
        self._clients.clear()

    @property
    def pool_count(self) -> int:
        """Number of live per-loop clients. Exposed for leak monitoring."""
        return len(self._clients)

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

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """Store a JSON-serializable value with an optional TTL. nx=True: set if not exist, xx=True: set if exists."""
        if not self._redis:
            return False
        try:
            serialized = json.dumps(value, default=str)
            res = await self._redis.set(key, serialized, ex=ttl, nx=nx, xx=xx)
            return bool(res)
        except Exception as e:
            logger.warning("Cache SET failed for %s: %s", key, e)
            return False

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
        except Exception:
            logger.exception("Redis ping failed:")
            return False

    @property
    def is_active(self) -> bool:
        """Return True if the Redis client is initialized."""
        return self._redis is not None

    async def set_nx(self, key: str, value: str, ttl: int) -> bool:
        """Set a value only if it does not already exist (distributed lock helper).

        Returns:
            True if set successfully (lock acquired), False otherwise.
        """
        if not self._redis:
            return False
        try:
            res = await self._redis.set(key, value, ex=ttl, nx=True)
            return bool(res)
        except Exception as e:
            logger.warning("Cache SET_NX failed for %s: %s", key, e)
            return False

    async def incr_by_float(self, key: str, amount: float, ttl: int | None = None) -> float:
        """Increment a floating-point value. Sets TTL on new keys."""
        if not self._redis:
            return 0.0
        try:
            new_val = await self._redis.incrbyfloat(key, amount)
            if ttl is not None:
                await self._redis.expire(key, ttl)
            return float(new_val)
        except Exception as e:
            logger.warning("Cache INCR_BY_FLOAT failed for %s: %s", key, e)
            return 0.0

    async def incr(self, key: str, ttl: int | None = None) -> int:
        """Increment an integer value. Optionally sets TTL on new keys."""
        if not self._redis:
            return 0
        try:
            new_val = await self._redis.incr(key)
            if ttl is not None:
                await self._redis.expire(key, ttl)
            return int(new_val)
        except Exception as e:
            logger.warning("Cache INCR failed for %s: %s", key, e)
            return 0

    async def get_raw(self, key: str) -> str | None:
        """Get raw un-serialized string value from Redis."""
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.warning("Cache GET_RAW failed for %s: %s", key, e)
            return None

    async def set_raw(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set raw string value with optional TTL."""
        if not self._redis:
            return
        try:
            await self._redis.set(key, value, ex=ttl)
        except Exception as e:
            logger.warning("Cache SET_RAW failed for %s: %s", key, e)

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
