from unittest.mock import AsyncMock, patch

import pytest

from app.services.pipeline_cache import PipelineCache


def test_pipeline_cache_hashing():
    cache = PipelineCache()
    text = "  hello world\n"
    # content_hash normalizes spacing and line endings
    hash1 = cache.content_hash(text)
    hash2 = cache.content_hash("hello world")
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 length

    # composite_hash joins parts with :: and hashes them
    comp_hash = cache.composite_hash("part1", "part2")
    assert len(comp_hash) == 64


def test_pipeline_cache_key():
    cache = PipelineCache()
    # Test default key construction
    key = cache.cache_key(
        stage="event_extraction",
        model="gemini-2.5-flash-lite",
        prompt_version="v2",
        content_hash="abc123hash",
        temperature=0.1,
    )
    assert key == "llm_cache:event_extraction:gemini-2.5-flash-lite:v2:1.0.0:0.10:abc123hash"


@pytest.mark.asyncio
@patch("app.services.cache_service.cache_service.get", new_callable=AsyncMock)
async def test_pipeline_cache_get_hit(mock_cache_get):
    cache = PipelineCache()
    mock_cache_get.return_value = {"key": "val"}

    res = await cache.get(
        stage="event_extraction",
        model="gemini-2.5-flash-lite",
        prompt_version="v2",
        content_hash="abc123hash",
        temperature=0.1,
    )
    assert res == {"key": "val"}
    mock_cache_get.assert_called_once_with(
        "llm_cache:event_extraction:gemini-2.5-flash-lite:v2:1.0.0:0.10:abc123hash"
    )


@pytest.mark.asyncio
@patch("app.services.cache_service.cache_service.get", new_callable=AsyncMock)
async def test_pipeline_cache_get_miss(mock_cache_get):
    cache = PipelineCache()
    mock_cache_get.return_value = None

    res = await cache.get(
        stage="event_extraction",
        model="gemini-2.5-flash-lite",
        prompt_version="v2",
        content_hash="abc123hash",
        temperature=0.1,
    )
    assert res is None


@pytest.mark.asyncio
@patch("app.services.cache_service.cache_service.set", new_callable=AsyncMock)
async def test_pipeline_cache_set(mock_cache_set):
    cache = PipelineCache()

    await cache.set(
        stage="event_extraction",
        model="gemini-2.5-flash-lite",
        prompt_version="v2",
        content_hash="abc123hash",
        response_data={"key": "val"},
        temperature=0.1,
    )
    # verify it called set with 30-day (2592000s) cleanup TTL
    mock_cache_set.assert_called_once_with(
        "llm_cache:event_extraction:gemini-2.5-flash-lite:v2:1.0.0:0.10:abc123hash",
        {"key": "val"},
        ttl=2592000,
    )
