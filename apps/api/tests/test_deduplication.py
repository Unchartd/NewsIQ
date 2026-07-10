from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import ResponseError

from app.core.bloom_filter import URLBloomFilter
from app.core.fingerprint import compute_fingerprints


def test_compute_fingerprints():
    url = "https://example.com/news/123"
    title = " Test Title "
    body = "Test Body"

    # Should lowercase and strip before hashing
    fp1 = compute_fingerprints(url, title.lower().strip(), body.lower().strip())

    # Check stable deterministic hash
    assert "url_hash" in fp1
    assert "content_hash" in fp1

    # Same content, different URL
    url2 = "https://example.com/news/123?utm_source=twitter"
    fp2 = compute_fingerprints(url2, title.lower().strip(), body.lower().strip())

    assert fp1["url_hash"] != fp2["url_hash"]
    assert fp1["content_hash"] == fp2["content_hash"]

@pytest.mark.asyncio
async def test_bloom_filter_redisbloom():
    cache_service = MagicMock()
    cache_service._redis = AsyncMock()
    cache_service._redis.execute_command.return_value = 1

    bf = URLBloomFilter(cache_service)

    # Test add
    added = await bf.add("hash1")
    assert added is True
    cache_service._redis.execute_command.assert_called_with("BF.ADD", bf.KEY_BLOOM, "hash1")

    # Test exists
    cache_service._redis.execute_command.return_value = 0
    exists = await bf.exists("hash2")
    assert exists is False
    cache_service._redis.execute_command.assert_called_with("BF.EXISTS", bf.KEY_BLOOM, "hash2")

@pytest.mark.asyncio
async def test_bloom_filter_fallback():
    cache_service = MagicMock()
    cache_service._redis = AsyncMock()

    # Simulate RedisBloom not available
    def mock_execute_command(*args, **kwargs):
        raise ResponseError("unknown command 'BF.ADD'")

    cache_service._redis.execute_command.side_effect = mock_execute_command
    cache_service._redis.sadd.return_value = 1

    bf = URLBloomFilter(cache_service)
    added = await bf.add("hash1")

    assert added is True
    assert bf.use_bloom is False
    assert bf.metrics["fallback_used"] is True
    cache_service._redis.sadd.assert_called_with(bf.KEY_SET, "hash1")

    cache_service._redis.sismember.return_value = 1
    exists = await bf.exists("hash1")
    assert exists is True
    cache_service._redis.sismember.assert_called_with(bf.KEY_SET, "hash1")

@pytest.mark.asyncio
async def test_bloom_filter_rebuild():
    cache_service = MagicMock()
    cache_service._redis = AsyncMock()

    pipeline_mock = AsyncMock()
    cache_service._redis.pipeline = MagicMock(return_value=pipeline_mock)

    bf = URLBloomFilter(cache_service)

    session_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars().all.return_value = ["hash1", "hash2"]
    session_mock.execute.return_value = result_mock

    await bf.rebuild(session_mock)

    cache_service._redis.delete.assert_called_with(bf.KEY_BLOOM)
    pipeline_mock.execute_command.assert_any_call("BF.ADD", bf.KEY_BLOOM, "hash1")
    pipeline_mock.execute_command.assert_any_call("BF.ADD", bf.KEY_BLOOM, "hash2")
    pipeline_mock.execute.assert_called_once()
