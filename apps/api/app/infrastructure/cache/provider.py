"""Cache infrastructure provider.

Wraps the Redis-based CacheService behind a provider interface.
Exposes get/set/delete/ping for business logic that imports this provider.
"""

from __future__ import annotations

import time
from typing import Any

from app.services.cache_service import cache_service as _redis_cache


class CacheProvider:
    """Provides cache operations and health checks.

    Delegates to CacheService (Redis). Swapping to a different cache backend
    requires replacing only this class's implementation.
    """

    async def get(self, key: str) -> Any | None:
        return await _redis_cache.get(key)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        await _redis_cache.set(key, value, ttl)

    async def delete(self, *keys: str) -> None:
        await _redis_cache.delete(*keys)

    async def delete_pattern(self, pattern: str) -> None:
        await _redis_cache.delete_pattern(pattern)

    async def health_check(self) -> dict:
        """Return a health status dict for the cache connection."""
        t0 = time.monotonic()
        try:
            ok = await _redis_cache.ping()
            latency_ms = (time.monotonic() - t0) * 1000
            return {
                "status": "ok" if ok else "error",
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }


cache_provider = CacheProvider()
