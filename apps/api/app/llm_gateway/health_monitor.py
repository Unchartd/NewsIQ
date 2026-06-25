import logging
from datetime import datetime, timedelta

from app.llm_gateway.base_provider import APIKey

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors provider key health, manages cooldowns and failover triggers."""

    def __init__(self) -> None:
        # Key: key_hash, Value: count of consecutive errors
        self._consecutive_failures: dict[str, int] = {}

    def _get_key_hash(self, key: str) -> str:
        import hashlib

        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def report_success(self, api_key: APIKey) -> None:
        """Reset consecutive failure counter upon a successful request."""
        key_hash = self._get_key_hash(api_key.key)
        self._consecutive_failures[key_hash] = 0
        api_key.healthy = True
        api_key.cooldown_until = None

    def report_failure(self, api_key: APIKey, error_msg: str) -> None:
        """Process API failure, determining if cooldown or disabling is warranted."""
        key_hash = self._get_key_hash(api_key.key)
        self._consecutive_failures[key_hash] = self._consecutive_failures.get(key_hash, 0) + 1

        error_lower = error_msg.lower()

        # 1. 429 Rate Limit / Quota Exceeded Cooldown
        is_rate_limit = (
            "429" in error_lower
            or "rate limit" in error_lower
            or "quota" in error_lower
            or "resource exhausted" in error_lower
            or "too many requests" in error_lower
            or "resource_exhausted" in error_lower
        )

        if is_rate_limit:
            # Put on cooldown for 60 seconds
            api_key.cooldown_until = datetime.utcnow() + timedelta(seconds=60)
            logger.warning(
                "APIKey (%s) hit rate limit. Cooling down until %s. Error: %s",
                api_key.get_masked(),
                api_key.cooldown_until,
                error_msg,
            )
            return

        # 2. Authentication Failures (Mark Unhealthy)
        is_auth_error = (
            "401" in error_lower
            or "authentication" in error_lower
            or "api key not valid" in error_lower
            or "invalid api key" in error_lower
            or "forbidden" in error_lower
            or "403" in error_lower
        )

        if is_auth_error:
            api_key.healthy = False
            logger.critical(
                "APIKey (%s) authentication failed. Disabling key. Error: %s",
                api_key.get_masked(),
                error_msg,
            )
            return

        # 3. Repeated other failures (Mark Unhealthy after 3 consecutive failures)
        if self._consecutive_failures[key_hash] >= 3:
            api_key.healthy = False
            logger.error(
                "APIKey (%s) failed 3 consecutive times. Disabling key. Last error: %s",
                api_key.get_masked(),
                error_msg,
            )
            return

        # Single temporary failure (e.g. timeout): cool down briefly
        api_key.cooldown_until = datetime.utcnow() + timedelta(seconds=15)
        logger.warning(
            "APIKey (%s) failed once. Cooling down for 15s. Error: %s",
            api_key.get_masked(),
            error_msg,
        )

    def trigger_heartbeat_check(self, api_key: APIKey) -> bool:
        """Periodic background checks to revive cooled down or disabled keys (could run a cheap model check)."""
        # If the cooldown has passed, remove the cooldown
        if api_key.cooldown_until and datetime.utcnow() > api_key.cooldown_until:
            api_key.cooldown_until = None
            logger.info("APIKey (%s) cooldown expired. Restoring to pool.", api_key.get_masked())
            return True
        return False
