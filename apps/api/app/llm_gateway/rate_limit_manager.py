import logging
import time

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitManager:
    """Tracks and enforces requests per minute (RPM) and requests per day (RPD) limits."""

    def __init__(self) -> None:
        self.redis_client = None
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            logger.info("RateLimitManager configured with Redis backend.")
        except Exception as e:
            logger.warning(
                "RateLimitManager Redis connection failed (falling back to memory): %s", e
            )

        # Local memory fallback structure
        # Key: key_hash, Value: list of timestamps of calls made
        self._memory_runs: dict[str, list[float]] = {}

    def _get_key_hash(self, key: str) -> str:
        """Create a simple hash of the key for caching/storing in Redis."""
        import hashlib

        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def check_rate_limit(self, key: str, rpm: int, rpd: int) -> bool:
        """Return True if the key is within rate limits (RPM, RPD), False otherwise."""
        key_hash = self._get_key_hash(key)
        now = time.time()

        if self.redis_client:
            try:
                # 1. RPM Check (sliding window - last 60 seconds)
                min_key = f"newsiq:rl:rpm:{key_hash}"
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(min_key, 0, now - 60)
                pipe.zcard(min_key)
                _, rpm_count = pipe.execute()

                if rpm_count >= rpm:
                    return False

                # 2. RPD Check (sliding window - last 86400 seconds)
                day_key = f"newsiq:rl:rpd:{key_hash}"
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(day_key, 0, now - 86400)
                pipe.zcard(day_key)
                _, rpd_count = pipe.execute()

                if rpd_count >= rpd:
                    return False

                return True
            except Exception as e:
                logger.warning(
                    "RateLimitManager Redis check failed, falling back to memory check: %s", e
                )

        # Local Memory Fallback
        if key_hash not in self._memory_runs:
            self._memory_runs[key_hash] = []

        # Filter out old runs
        self._memory_runs[key_hash] = [t for t in self._memory_runs[key_hash] if t > now - 86400]
        recent_day = self._memory_runs[key_hash]
        recent_min = [t for t in recent_day if t > now - 60]

        if len(recent_min) >= rpm:
            return False
        if len(recent_day) >= rpd:
            return False

        return True

    def record_request(self, key: str) -> None:
        """Record a successful request timestamp to the rate limiter."""
        key_hash = self._get_key_hash(key)
        now = time.time()

        if self.redis_client:
            try:
                min_key = f"newsiq:rl:rpm:{key_hash}"
                day_key = f"newsiq:rl:rpd:{key_hash}"

                pipe = self.redis_client.pipeline()
                pipe.zadd(min_key, {str(now): now})
                pipe.expire(min_key, 120)
                pipe.zadd(day_key, {str(now): now})
                pipe.expire(day_key, 90000)
                pipe.execute()
                return
            except Exception as e:
                logger.warning(
                    "RateLimitManager Redis record failed, falling back to memory: %s", e
                )

        # Local Memory Fallback
        if key_hash not in self._memory_runs:
            self._memory_runs[key_hash] = []
        self._memory_runs[key_hash].append(now)
