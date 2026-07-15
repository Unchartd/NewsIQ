import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.extraction.types import (
    ExtractionDiagnostics,
    ExtractionFailure,
    ExtractionResult,
)
from app.services.extraction_manager import ExtractionManager


class MockRedis:
    def __init__(self):
        self.store = {}
        self.lists = {}
        self.lock = asyncio.Lock()

    async def get(self, key):
        async with self.lock:
            return self.store.get(key)

    async def set(self, key, value, ex=None, nx=False, xx=False):
        async with self.lock:
            if nx and key in self.store:
                return None
            self.store[key] = str(value)
            return "OK"

    async def rpush(self, key, value):
        async with self.lock:
            if key not in self.lists:
                self.lists[key] = []
            self.lists[key].append(value)
            return len(self.lists[key])

    async def llen(self, key):
        async with self.lock:
            return len(self.lists.get(key, []))

    async def lpop(self, key):
        async with self.lock:
            if key in self.lists and self.lists[key]:
                return self.lists[key].pop(0)
            return None

    async def delete(self, key):
        async with self.lock:
            self.store.pop(key, None)
            self.lists.pop(key, None)
            return 1

    async def lrem(self, key, count, value):
        async with self.lock:
            if key in self.lists:
                try:
                    self.lists[key].remove(value)
                    return 1
                except ValueError:
                    pass
            return 0


@pytest.mark.asyncio
async def test_tavily_batch_concurrency_and_leader_election():
    """Verify that multiple concurrent requests do not deadlock, elect leaders, and drain the queue."""
    manager = ExtractionManager()
    mock_redis = MockRedis()

    # Mock the Tavily provider methods
    async def mock_extract_batch(urls, exec_ids):
        # Simulate Tavily batch extraction time
        await asyncio.sleep(0.1)
        results = []
        for url, exec_id in zip(urls, exec_ids):
            results.append(
                ExtractionResult(
                    success=True,
                    provider="tavily",
                    failure=ExtractionFailure.SUCCESS,
                    url=url,
                    title=f"Title for {url}",
                    content="Extracted batch content.",
                    author=None,
                    image_url=None,
                    published_at=None,
                    diagnostics=ExtractionDiagnostics(
                        provider="tavily",
                        attempts=1,
                        latency_ms=50.0,
                        status_code=200,
                        bot_detected=False,
                        notes=[],
                    ),
                )
            )
        return results

    manager.tavily_provider = AsyncMock()
    manager.tavily_provider.extract_batch.side_effect = mock_extract_batch
    manager.tavily_provider.extract.return_value = ExtractionResult(
        success=False,
        provider="tavily",
        failure=ExtractionFailure.TIMEOUT,
        url="",
        title=None,
        content="",
        author=None,
        image_url=None,
        published_at=None,
        diagnostics=ExtractionDiagnostics(
            provider="tavily",
            attempts=1,
            latency_ms=10.0,
            status_code=None,
            bot_detected=False,
            notes=["Fallback invoked"],
        ),
    )

    with patch("app.services.extraction_manager.cache_service") as mock_cache:
        mock_cache._redis = mock_redis

        # Configure batch settings for fast testing: batch size 3, timeout 0.5s
        with patch("app.core.config.settings.TAVILY_BATCH_SIZE", 3), \
             patch("app.core.config.settings.TAVILY_BATCH_TIMEOUT_SECONDS", 0.5):

            # Spawn 6 concurrent requests
            urls = [f"https://example.com/art-{i}" for i in range(6)]
            exec_ids = [f"exec-{i}" for i in range(6)]

            tasks = [
                manager.extract_via_tavily_batch(url, exec_id)
                for url, exec_id in zip(urls, exec_ids)
            ]

            results = await asyncio.gather(*tasks)

            # Assertions
            assert len(results) == 6
            for r in results:
                assert r.success is True
                assert r.provider == "tavily"

            # Check that the batch was drained completely from Redis
            buffer_len = await mock_redis.llen("extraction:tavily_buffer")
            assert buffer_len == 0

            # Leader lock should be deleted
            leader_lock = await mock_redis.get("extraction:tavily_leader")
            assert leader_lock is None
