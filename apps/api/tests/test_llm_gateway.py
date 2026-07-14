from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm_gateway.base_provider import APIKey, GatewayResponse
from app.llm_gateway.cost_tracker import CostTracker
from app.llm_gateway.fallback_chain import FallbackChain
from app.llm_gateway.health_monitor import HealthMonitor
from app.llm_gateway.provider_pool import APIKeyPool, GeminiProvider
from app.llm_gateway.provider_router import ProviderRouter
from app.llm_gateway.rate_limit_manager import RateLimitManager
from app.llm_gateway.request_manager import RequestManager


def test_api_key_model():
    key = APIKey(
        key="test-key-123", provider="google", requests_per_minute=10, requests_per_day=100
    )
    assert key.is_cooling_down() is False
    assert key.get_masked() == "test...-123"

    key.cooldown_until = datetime.utcnow() + timedelta(seconds=10)
    assert key.is_cooling_down() is True

    key.cooldown_until = datetime.utcnow() - timedelta(seconds=10)
    assert key.is_cooling_down() is False


@patch("app.llm_gateway.provider_pool.settings")
def test_api_key_pool_loading(mock_settings):
    mock_settings.GEMINI_API_KEY_SYNTH = "key1,key2"
    mock_settings.GEMINI_API_KEY = None
    mock_settings.OPENAI_API_KEY = "op1"

    pool = APIKeyPool()
    google_keys = pool.get_keys("google")
    assert len(google_keys) == 2
    assert google_keys[0].key == "key1"
    assert google_keys[1].key == "key2"

    openai_keys = pool.get_keys("openai")
    assert len(openai_keys) == 1
    assert openai_keys[0].key == "op1"


def test_rate_limit_manager_in_memory():
    # Force memory fallback by disabling Redis
    rl = RateLimitManager()
    rl.redis_client = None

    key = "test-rl-key"
    assert rl.check_rate_limit(key, rpm=2, rpd=10) is True

    rl.record_request(key)
    assert rl.check_rate_limit(key, rpm=2, rpd=10) is True

    rl.record_request(key)
    # RPM is 2, and we recorded 2 requests
    assert rl.check_rate_limit(key, rpm=2, rpd=10) is False


def test_health_monitor_cooldowns_and_disabling():
    hm = HealthMonitor()
    key = APIKey(
        key="test-key-health", provider="google", requests_per_minute=10, requests_per_day=100
    )

    # Success resets everything
    hm.report_success(key)
    assert key.healthy is True
    assert key.cooldown_until is None

    # 429 error triggers cooldown
    hm.report_failure(key, "Error 429: Resource exhausted")
    assert key.is_cooling_down() is True
    assert key.healthy is True

    # Reset
    hm.report_success(key)

    # 401 error disables key
    hm.report_failure(key, "Error 401: Invalid API Key")
    assert key.healthy is False
    assert key.cooldown_until is None

    # Reset
    hm.report_success(key)

    # 3 consecutive other failures disable key
    hm.report_failure(key, "Timeout")
    assert key.healthy is True  # 1 failure
    hm.report_failure(key, "Timeout")
    assert key.healthy is True  # 2 failures
    hm.report_failure(key, "Timeout")
    assert key.healthy is False  # 3 failures


def test_provider_router():
    pool = APIKeyPool()
    rl = RateLimitManager()
    rl.redis_client = None
    hm = HealthMonitor()

    # Setup keys in pool manually
    key1 = APIKey(key="k1", provider="google", requests_per_minute=5, requests_per_day=50)
    key2 = APIKey(key="k2", provider="google", requests_per_minute=5, requests_per_day=50)
    pool.pools["google"] = [key1, key2]

    router = ProviderRouter(pool, rl, hm)

    # Both healthy, should pick first one
    selected, client = router.select_key_and_client("google", "gemini-2.5-flash-lite")
    assert selected.key == "k1"
    assert isinstance(client, GeminiProvider)

    # Put key1 on cooldown
    key1.cooldown_until = datetime.utcnow() + timedelta(seconds=10)
    selected, _ = router.select_key_and_client("google", "gemini-2.5-flash-lite")
    assert selected.key == "k2"  # key2 chosen since key1 is cooling down

    # Put both on cooldown: should pick the one with earliest expiration (key1)
    key2.cooldown_until = datetime.utcnow() + timedelta(seconds=20)
    selected, _ = router.select_key_and_client("google", "gemini-2.5-flash-lite")
    assert selected.key == "k1"


def test_fallback_chain():
    chain = FallbackChain()
    fc = chain.get_fallback_chain("gemini-2.5-flash-lite")
    assert len(fc) == 7
    assert fc[0] == {"provider": "google", "model": "gemini-2.5-flash-lite"}
    assert fc[6] == {"provider": "mock", "model": "mock"}

    fc_gpt = chain.get_fallback_chain("gpt-4o-mini")
    assert fc_gpt[0] == {"provider": "openai", "model": "gpt-4o-mini"}


def test_cost_tracker():
    tracker = CostTracker()
    cost = tracker.calculate_cost("gemini-2.5-flash-lite", 100_000, 200_000)
    # input: 0.075 / M -> 0.075 * 0.1 = 0.0075
    # output: 0.30 / M -> 0.30 * 0.2 = 0.06
    # total = 0.0675
    assert cost == 0.0675


@pytest.mark.asyncio
@patch("app.llm_gateway.request_manager.track_llm_call")
async def test_request_manager_fallback_execution(mock_track_call):
    from app.core.config import settings

    with patch.object(settings, "USE_NEW_GATEWAY", False):
        # Mock database trace context manager
        mock_trace = MagicMock()
        mock_trace.response_text = ""
        mock_trace.input_tokens = 0
        mock_trace.output_tokens = 0
        mock_trace.total_tokens = 0
        mock_trace.status = "success"
        mock_trace.cost_usd = 0.0
        mock_trace.error = None

        # Setup the async context manager mock
        async_context_mock = AsyncMock()
        async_context_mock.__aenter__.return_value = mock_trace
        async_context_mock.__aexit__.return_value = None
        mock_track_call.return_value = async_context_mock

        manager = RequestManager()
        manager.key_pool.pools["google"] = [APIKey(key="g-key", provider="google")]
        manager.key_pool.pools["groq"] = [APIKey(key="gr-key", provider="groq")]

        # Mock the providers to fail for Gemini, and succeed for Groq/OpenAI fallback
        gemini_client = AsyncMock()
        gemini_client.execute.return_value = GatewayResponse(
            content="",
            provider="google",
            model="gemini-2.5-flash-lite",
            error="429 Resource Exhausted",
        )

        groq_client = AsyncMock()
        groq_client.execute.return_value = GatewayResponse(
            content="Success from Groq",
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
        )

        manager.router.clients["google"] = gemini_client
        manager.router.clients["groq"] = groq_client

        # Execute request requesting gemini-2.5-flash-lite
        response = await manager.execute_request(
            model="gemini-2.5-flash-lite",
            stage="test_stage",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # Groq was executed successfully as fallback
        assert response.content == "Success from Groq"
        assert response.provider == "groq"
        assert response.model == "llama-3.1-8b-instant"
        assert response.cost_usd > 0.0

        # Ensure gemini failed and health monitor was notified
        assert gemini_client.execute.called
    assert groq_client.execute.called
