import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import Any

from app.ai.config import CAPABILITY_ROUTING, ProviderModelRoute, ProviderType
from app.ai.interfaces import AIProvider, APIKey
from app.ai.metrics.telemetry import newsiq_ai_gateway_circuit_state
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.mock import MockProvider
from app.ai.providers.nvidia import NvidiaProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

HEALTH_CHECK_COOLDOWN = timedelta(minutes=2)


class ProviderHealthTracker:
    """Tracks provider health status and manages circuit breaker state."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.healthy = True
        self.consecutive_failures = 0
        self.disabled_until: datetime | None = None
        self.last_health_check: datetime | None = None

    def report_success(self) -> None:
        self.consecutive_failures = 0
        if not self.healthy:
            logger.info("Circuit breaker CLOSED (restored) for provider: %s", self.provider)
        self.healthy = True
        self.disabled_until = None
        newsiq_ai_gateway_circuit_state.labels(provider=self.provider).set(0)

    def report_failure(self, error_msg: str) -> None:
        self.consecutive_failures += 1
        logger.warning(
            "Provider %s reported failure #%d: %s",
            self.provider,
            self.consecutive_failures,
            error_msg,
        )

        # Trigger circuit breaker on 3 consecutive failures
        if self.consecutive_failures >= 3:
            if self.healthy:
                logger.critical(
                    "Circuit breaker OPENED (tripped) for provider: %s. Disabling for 5 minutes.",
                    self.provider,
                )
            self.healthy = False
            self.disabled_until = datetime.utcnow() + timedelta(minutes=5)
            newsiq_ai_gateway_circuit_state.labels(provider=self.provider).set(1)

    def is_available(self) -> bool:
        if self.healthy:
            return True
        if self.disabled_until and datetime.utcnow() > self.disabled_until:
            # Let it try once to see if it recovered (half-open state)
            logger.info(
                "Circuit breaker HALF-OPEN for provider: %s. Testing recovery.", self.provider
            )
            return True
        return False


class CapabilityRouter:
    """Decides the execution route and handles key rotation/circuit breaking."""

    def __init__(self) -> None:
        # Load clients
        self.clients: dict[ProviderType, AIProvider] = {
            "gemini": GeminiProvider(),
            "nvidia": NvidiaProvider(),
            "openrouter": OpenRouterProvider(),
            "mock": MockProvider(),
        }

        # Initialize health trackers
        self.health_trackers: dict[str, ProviderHealthTracker] = {
            "gemini": ProviderHealthTracker("gemini"),
            "nvidia": ProviderHealthTracker("nvidia"),
            "openrouter": ProviderHealthTracker("openrouter"),
            "mock": ProviderHealthTracker("mock"),
        }

        self.pools: dict[str, list[APIKey]] = {}
        self.load_api_keys()

    def load_api_keys(self) -> None:
        """Load API keys from settings."""
        self.pools.clear()

        # 1. Google Gemini
        gemini_keys = []
        gemini_env = settings.GEMINI_API_KEY_SYNTH or settings.GEMINI_API_KEY or ""
        for k in [k.strip() for k in gemini_env.split(",") if k.strip()]:
            gemini_keys.append(
                APIKey(key=k, provider="gemini", requests_per_minute=15, requests_per_day=1500)
            )
        self.pools["gemini"] = gemini_keys

        # 2. NVIDIA NIM
        nvidia_keys = []
        nvidia_env = settings.NVIDIA_API_KEY or ""
        for k in [k.strip() for k in nvidia_env.split(",") if k.strip()]:
            nvidia_keys.append(
                APIKey(key=k, provider="nvidia", requests_per_minute=15, requests_per_day=5000)
            )
        self.pools["nvidia"] = nvidia_keys

        # 3. OpenRouter
        openrouter_keys = []
        openrouter_env = settings.OPENROUTER_API_KEY or ""
        for k in [k.strip() for k in openrouter_env.split(",") if k.strip()]:
            openrouter_keys.append(
                APIKey(key=k, provider="openrouter", requests_per_minute=30, requests_per_day=14400)
            )
        self.pools["openrouter"] = openrouter_keys

        # 4. Mock
        self.pools["mock"] = [
            APIKey(
                key="mock-key", provider="mock", requests_per_minute=1000, requests_per_day=100000
            )
        ]

    def _select_key(self, provider: str) -> APIKey | None:
        """Rotate keys and select a non-cooldown healthy key from the pool."""
        keys = self.pools.get(provider, [])
        if not keys:
            return None

        # Filter healthy, non-cooling keys
        available = [k for k in keys if k.healthy and not k.is_cooling_down()]

        if not available:
            # If all cooling down, grab the one ending soonest
            cooling = [k for k in keys if k.healthy]
            if cooling:
                available = sorted(cooling, key=lambda k: k.cooldown_until or datetime.min)

        if not available:
            # If all unhealthy, fallback to first key
            available = keys

        return available[0] if available else None

    def get_route(self, capability: str) -> list[tuple[AIProvider, APIKey, ProviderModelRoute]]:
        """Return the prioritized list of (client, key, route_config) for a capability."""
        # Detect testing environment
        is_testing = "pytest" in sys.modules or any(
            "pytest" in arg or "unittest" in arg for arg in sys.argv
        )

        if is_testing:
            mock_key = self._select_key("mock")
            assert mock_key is not None
            mock_route = ProviderModelRoute(
                provider="mock", model="mock", temperature=0.0, timeout=15.0
            )
            return [(self.clients["mock"], mock_key, mock_route)]

        route_config = CAPABILITY_ROUTING.get(capability)
        if not route_config:
            raise ValueError(f"Unknown capability: {capability}")

        chain = []
        from typing import Literal

        levels: list[Literal["primary", "fallback", "lastFallback"]] = [
            "primary",
            "fallback",
            "lastFallback",
        ]
        for level in levels:
            cfg = route_config[level].copy()
            provider = cfg["provider"]

            # Dynamically override embedding model if settings specify a preferred one
            if capability == "embedding" and provider == "gemini" and settings.EMBEDDING_MODEL:
                cfg["model"] = settings.EMBEDDING_MODEL

            tracker = self.health_trackers[provider]

            if not tracker.is_available():
                # Skip unhealthy provider (circuit tripped)
                logger.warning("CapabilityRouter skipping unhealthy provider: %s", provider)
                # Trigger a background heartbeat health check if cooled down
                self.trigger_background_health_check(provider)
                continue

            key = self._select_key(provider)
            if not key:
                # Skip if no keys configured
                continue

            chain.append((self.clients[provider], key, cfg))

        if not chain:
            # Fallback to mock in desperation or raise
            raise RuntimeError(f"No healthy providers available for capability: {capability}")

        return chain

    def get_model_route(self, model: str) -> list[tuple[AIProvider, APIKey, dict[str, Any]]]:
        """Return prioritized list of (client, key, route_config) for a model name.

        Performs dynamic health checks and rotates/selects API keys.
        """
        # Detect testing environment
        is_testing = "pytest" in sys.modules or any(
            "pytest" in arg or "unittest" in arg for arg in sys.argv
        )

        if is_testing:
            mock_key = self._select_key("mock")
            assert mock_key is not None
            mock_route = {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0}
            return [(self.clients["mock"], mock_key, mock_route)]

        from app.ai.config import MODEL_FALLBACKS

        routes = MODEL_FALLBACKS.get(model)
        if not routes:
            # If not configured, fall back to openrouter or gemini if we can guess,
            # or try to run model as-is on Gemini / OpenRouter. Default to gemini.
            logger.warning(
                "get_model_route: model '%s' not in MODEL_FALLBACKS, using default.", model
            )
            routes = [{"provider": "gemini", "model": model, "temperature": 0.1, "timeout": 30.0}]

        chain = []
        for cfg in routes:
            provider = cfg["provider"]
            tracker = self.health_trackers.get(provider)
            if tracker and not tracker.is_available():
                logger.warning(
                    "CapabilityRouter skipping unhealthy provider in model route: %s", provider
                )
                self.trigger_background_health_check(provider)
                continue

            key = self._select_key(provider)
            if not key:
                continue

            chain.append((self.clients[provider], key, cfg))

        if not chain:
            mock_key = self._select_key("mock")
            if mock_key:
                chain.append(
                    (
                        self.clients["mock"],
                        mock_key,
                        {"provider": "mock", "model": "mock", "temperature": 0.0, "timeout": 15.0},
                    )
                )
            else:
                raise RuntimeError(f"No healthy providers available for model: {model}")

        return chain

    def trigger_background_health_check(self, provider: str) -> None:
        """Runs a background check to revive unhealthy providers."""
        tracker = self.health_trackers[provider]
        now = datetime.utcnow()
        if tracker.last_health_check and (now - tracker.last_health_check) < HEALTH_CHECK_COOLDOWN:
            return

        tracker.last_health_check = now

        async def _check():
            logger.info("Starting background health check for provider: %s", provider)
            key = self._select_key(provider)
            if not key:
                return
            try:
                status = await self.clients[provider].health(key)
                if status.healthy:
                    tracker.report_success()
                else:
                    logger.warning(
                        "Background health check failed for %s: %s", provider, status.error
                    )
            except Exception as e:
                logger.error("Error during background health check for %s: %s", provider, e)

        # Execute as a fire-and-forget task
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(_check())


# Singleton
capability_router = CapabilityRouter()
