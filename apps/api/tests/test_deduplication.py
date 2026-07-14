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


def test_compute_fingerprints_none_body():
    """BUG-03 regression: None body/title must not produce the string 'None' in the hash.

    Before the fix, compute_fingerprints(url, title, None) would embed the literal
    string 'None' in the hash payload, causing:
    - Different hashes for the same content when None vs "" is passed.
    - Potential false-match collisions when titles match but content failed to extract.
    """
    url = "https://example.com/article"

    # None body should hash identically to empty string body
    fp_none = compute_fingerprints(url, "some title", None)
    fp_empty = compute_fingerprints(url, "some title", "")
    assert fp_none["content_hash"] == fp_empty["content_hash"], (
        "None body must hash the same as empty string body"
    )

    # None title should hash identically to empty string title
    fp_none_title = compute_fingerprints(url, None, "some body")
    fp_empty_title = compute_fingerprints(url, "", "some body")
    assert fp_none_title["content_hash"] == fp_empty_title["content_hash"], (
        "None title must hash the same as empty string title"
    )

    # Both None
    fp_both_none = compute_fingerprints(url, None, None)
    fp_both_empty = compute_fingerprints(url, "", "")
    assert fp_both_none["content_hash"] == fp_both_empty["content_hash"]

    # The hash must NOT contain the string "None" — verify by hashing known good value
    import hashlib
    bad_payload = "some title\n\nNone"
    bad_hash = hashlib.sha256(bad_payload.encode("utf-8")).hexdigest()
    assert fp_none["content_hash"] != bad_hash, (
        "content_hash must not be derived from the string 'None'"
    )



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
