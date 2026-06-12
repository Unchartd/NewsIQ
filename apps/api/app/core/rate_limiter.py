"""Redis-based rate limiting middleware."""

import time
import logging
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to rate limit requests using a fixed-window counter in Redis."""

    def __init__(self, app, limit: int = 100, window: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.redis = None
        if settings.REDIS_URL:
            try:
                self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            except Exception as e:
                logger.error(f"Failed to initialize Redis for rate limiting: {e}")

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health/ready probes or if Redis client isn't available
        if not self.redis or request.url.path in ["/health", "/ready", "/docs", "/redoc"]:
            return await call_next(request)

        # Allow testing environment to bypass rate limits
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
                logger.warning(f"Rate limit exceeded for client IP: {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Rate limit exceeded."},
                    headers={"Retry-After": str(self.window)},
                )
        except Exception as e:
            # Fails open so that temporary Redis connectivity issues do not take down the API
            logger.error(f"Error checking rate limits in Redis: {e}")

        return await call_next(request)
