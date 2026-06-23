import logging
from typing import Dict, Tuple, List, Optional
from datetime import datetime

from app.llm_gateway.base_provider import BaseLLMProvider, APIKey
from app.llm_gateway.provider_pool import APIKeyPool, GeminiProvider, OpenAIProvider, MockProvider
from app.llm_gateway.rate_limit_manager import RateLimitManager
from app.llm_gateway.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)

class ProviderRouter:
    """Routes requests to the best available provider client and API key."""

    def __init__(
        self,
        key_pool: APIKeyPool,
        rate_limiter: RateLimitManager,
        health_monitor: HealthMonitor
    ) -> None:
        self.key_pool = key_pool
        self.rate_limiter = rate_limiter
        self.health_monitor = health_monitor

        # Initialise provider client instances
        self.clients: Dict[str, BaseLLMProvider] = {
            "google": GeminiProvider(),
            "openai": OpenAIProvider(provider_name="openai"),
            "groq": OpenAIProvider(provider_name="groq", base_url="https://api.groq.com/openai/v1"),
            "cerebras": OpenAIProvider(provider_name="cerebras", base_url="https://api.cerebras.ai/v1"),
            "nvidia": OpenAIProvider(provider_name="nvidia", base_url="https://integrate.api.nvidia.com/v1"),
            "mock": MockProvider()
        }

    def select_key_and_client(self, provider: str, model: str) -> Tuple[APIKey, BaseLLMProvider]:
        """Select a healthy, non-cooling API key and its client for a provider."""
        client = self.clients.get(provider)
        if not client:
            raise ValueError(f"Unsupported provider: {provider}")

        keys = self.key_pool.get_keys(provider)
        if not keys:
            if provider == "mock":
                # Fallback mock key if none exists (should not happen)
                mock_key = APIKey(key="mock-key-default", provider="mock")
                return mock_key, self.clients["mock"]
            raise RuntimeError(f"No API keys configured for provider: {provider}")

        # Try to revive keys whose cooldown has expired
        for key in keys:
            self.health_monitor.trigger_heartbeat_check(key)

        # Filter: healthy keys
        healthy_keys = [k for k in keys if k.healthy]
        if not healthy_keys:
            logger.error("All keys for provider %s are flagged UNHEALTHY. Attempting fallback on last key.", provider)
            # Fallback: return first key anyway to try, or let exception be raised
            healthy_keys = keys

        # Filter: keys not in cooldown
        available_keys = [k for k in healthy_keys if not k.is_cooling_down()]
        
        # If all keys are in cooldown, grab the one that finishes cooling down earliest
        if not available_keys:
            logger.warning("All keys for provider %s are in cooldown. Selecting key with earliest cooldown expiration.", provider)
            available_keys = sorted(
                healthy_keys,
                key=lambda k: k.cooldown_until or datetime.min
            )

        # Filter: Rate limiter limits check
        rate_ok_keys = []
        for key in available_keys:
            if self.rate_limiter.check_rate_limit(key.key, key.requests_per_minute, key.requests_per_day):
                rate_ok_keys.append(key)

        # If rate limits block all keys, fall back to the available keys
        final_candidates = rate_ok_keys if rate_ok_keys else available_keys

        # Selection strategy: Least loaded (for in-memory tracking) or first available
        # In a multi-key environment, we can do a simple round-robin or first available.
        # Since we record usage, we pick the first candidate here.
        selected_key = final_candidates[0]
        
        logger.debug(
            "Selected key %s for provider %s (candidates: %d/%d)",
            selected_key.get_masked(), provider, len(final_candidates), len(keys)
        )
        return selected_key, client
