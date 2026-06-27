"""Redis-based rate limiting middleware.

Uses a fixed-window counter in Redis. Fails open: if Redis is unavailable,
requests pass through so temporary Redis connectivity issues don't take
down the API.

TLS / Upstash support:
  Automatically detects rediss:// scheme and enables TLS.
"""

import logging
import ssl
import time

import redis.asyncio as aioredis
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

# Paths that are always exempt from rate limiting
_EXEMPT_PATHS = frozenset(
    {
        "/health",
        "/health/database",
        "/health/cache",
        "/health/storage",
        "/health/llm",
        "/health/search",
        "/health/observability",
        "/ready",
        "/docs",
        "/redoc",
        "/metrics",
    }
)


def _make_rate_limit_client(url: str) -> aioredis.Redis | None:
    """Create an async Redis client for rate limiting with automatic TLS support."""
    if not url:
        return None
    try:
        kwargs: dict = {"decode_responses": True}
        if url.startswith("rediss://"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs["ssl_context"] = ctx
        return aioredis.from_url(url, **kwargs)
    except Exception as e:
        logger.error("Failed to initialize Redis for rate limiting: %s", e)
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to rate limit requests using a fixed-window counter in Redis."""

    def __init__(self, app, limit: int = 100, window: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.redis = _make_rate_limit_client(settings.REDIS_URL)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health/ready probes or if Redis client isn't available
        if not self.redis or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Allow bypass only in DEBUG mode for the test suite. Never bypass in production.
        if settings.DEBUG:
            user_agent = request.headers.get("user-agent", "").lower()
            if "test" in user_agent or "pytest" in user_agent:
                return await call_next(request)

        # Client key definition
        client_ip = request.client.host if request.client else "unknown"
        current_window = int(time.time() / self.window)
        key = f"rate_limit:{client_ip}:{current_window}"

        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, self.window + 10)
                results = await pipe.execute()
                request_count = results[0]

            if request_count > self.limit:
                logger.warning("Rate limit exceeded for client IP: %s", client_ip)
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Rate limit exceeded."},
                    headers={"Retry-After": str(self.window)},
                )
        except Exception as e:
            # Fails open so that temporary Redis connectivity issues do not take down the API
            logger.error("Error checking rate limits in Redis: %s", e)

        return await call_next(request)
