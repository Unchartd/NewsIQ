import json
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

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None, nx=False, xx=False):
        if nx and key in self.store:
            return None
        self.store[key] = str(value)
        return "OK"

    async def rpush(self, key, value):
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key].append(value)
        return len(self.lists[key])

    async def llen(self, key):
        return len(self.lists.get(key, []))

    async def lpop(self, key):
        if key in self.lists and self.lists[key]:
            return self.lists[key].pop(0)
        return None

    async def delete(self, key):
        self.store.pop(key, None)
        self.lists.pop(key, None)
        return 1


@pytest.mark.asyncio
async def test_local_success_skips_apis():
    """Verify that local crawler success skips external APIs."""
    manager = ExtractionManager()
    url = "https://example.com/local-success"

    mock_local = AsyncMock()
    mock_local.extract.return_value = ExtractionResult(
        success=True,
        provider="local",
        failure=ExtractionFailure.SUCCESS,
        url=url,
        title="Local Title",
        content="This is local content that is long enough to be valid.",
        author=None,
        image_url=None,
        published_at=None,
        diagnostics=ExtractionDiagnostics(
            provider="local",
            attempts=1,
            latency_ms=10.0,
            status_code=200,
            bot_detected=False,
            notes=[],
        ),
    )

    mock_tavily = AsyncMock()
    mock_firecrawl = AsyncMock()

    manager.local_provider = mock_local
    manager.tavily_provider = mock_tavily
    manager.firecrawl_provider = mock_firecrawl

    with patch("app.services.extraction_manager.cache_service") as mock_cache:
        mock_cache._redis = None
        result = await manager.crawl_article(url)

        assert result["success"] is True
        assert result["title"] == "Local Title"
        assert result["extractor"] == "local"

        mock_local.extract.assert_called_once()
        mock_tavily.extract.assert_not_called()
        mock_firecrawl.extract.assert_not_called()


@pytest.mark.asyncio
async def test_local_404_stops_immediately():
    """Verify that a 404 failure stops the extraction chain immediately."""
    manager = ExtractionManager()
    url = "https://example.com/not-found"

    mock_local = AsyncMock()
    mock_local.extract.return_value = ExtractionResult(
        success=False,
        provider="local",
        failure=ExtractionFailure.HTTP_404,
        url=url,
        title=None,
        content="",
        author=None,
        image_url=None,
        published_at=None,
        diagnostics=ExtractionDiagnostics(
            provider="local",
            attempts=1,
            latency_ms=10.0,
            status_code=404,
            bot_detected=False,
            notes=[],
        ),
    )

    mock_tavily = AsyncMock()
    mock_firecrawl = AsyncMock()

    manager.local_provider = mock_local
    manager.tavily_provider = mock_tavily
    manager.firecrawl_provider = mock_firecrawl

    with patch("app.services.extraction_manager.cache_service") as mock_cache:
        mock_cache._redis = None
        result = await manager.crawl_article(url)

        assert result["success"] is False
        assert result["diagnostics"]["status_code"] == 404
        assert result["diagnostics"]["failure_reason"] == "HTTP_ERROR"

        mock_local.extract.assert_called_once()
        mock_tavily.extract.assert_not_called()
        mock_firecrawl.extract.assert_not_called()


@pytest.mark.asyncio
async def test_tavily_failure_falls_back_to_firecrawl():
    """Verify that a Tavily batch failure falls back to Firecrawl scraping."""
    manager = ExtractionManager()
    url = "https://example.com/tavily-fail"

    mock_local = AsyncMock()
    mock_local.extract.return_value = ExtractionResult(
        success=False,
        provider="local",
        failure=ExtractionFailure.TIMEOUT,
        url=url,
        title=None,
        content="",
        author=None,
        image_url=None,
        published_at=None,
        diagnostics=ExtractionDiagnostics(
            provider="local",
            attempts=1,
            latency_ms=10.0,
            status_code=None,
            bot_detected=False,
            notes=[],
        ),
    )

    mock_tavily = AsyncMock()
    mock_tavily.extract.return_value = ExtractionResult(
        success=False,
        provider="tavily",
        failure=ExtractionFailure.TIMEOUT,
        url=url,
        title=None,
        content="",
        author=None,
        image_url=None,
        published_at=None,
        diagnostics=ExtractionDiagnostics(
            provider="tavily",
            attempts=1,
            latency_ms=20.0,
            status_code=None,
            bot_detected=False,
            notes=[],
        ),
    )

    mock_firecrawl = AsyncMock()
    mock_firecrawl.extract.return_value = ExtractionResult(
        success=True,
        provider="firecrawl",
        failure=ExtractionFailure.SUCCESS,
        url=url,
        title="Firecrawl Title",
        content="This content is extracted using Firecrawl scraping fallback.",
        author=None,
        image_url=None,
        published_at=None,
        diagnostics=ExtractionDiagnostics(
            provider="firecrawl",
            attempts=1,
            latency_ms=30.0,
            status_code=200,
            bot_detected=False,
            notes=[],
        ),
    )

    manager.local_provider = mock_local
    manager.tavily_provider = mock_tavily
    manager.firecrawl_provider = mock_firecrawl

    with patch("app.services.extraction_manager.cache_service") as mock_cache:
        mock_cache._redis = None
        result = await manager.crawl_article(url)

        assert result["success"] is True
        assert result["title"] == "Firecrawl Title"
        assert result["extractor"] == "firecrawl"

        mock_local.extract.assert_called_once()
        mock_tavily.extract.assert_called_once()
        mock_firecrawl.extract.assert_called_once()


@pytest.mark.asyncio
async def test_idempotency_cache():
    """Verify that cached extraction results are returned immediately without calling providers."""
    manager = ExtractionManager()
    url = "https://example.com/cached"

    mock_local = AsyncMock()
    manager.local_provider = mock_local

    cached_result = ExtractionResult(
        success=True,
        provider="tavily",
        failure=ExtractionFailure.SUCCESS,
        url=url,
        title="Cached Title",
        content="Cached content here.",
        author=None,
        image_url=None,
        published_at=None,
        diagnostics=ExtractionDiagnostics(
            provider="tavily",
            attempts=1,
            latency_ms=5.0,
            status_code=200,
            bot_detected=False,
            notes=[],
        ),
    )

    mock_redis = MockRedis()
    import hashlib

    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    await mock_redis.set(f"extraction:idempotency:{url_hash}", json.dumps(cached_result.to_dict()))

    with patch("app.services.extraction_manager.cache_service") as mock_cache:
        mock_cache._redis = mock_redis
        result = await manager.crawl_article(url)

        assert result["success"] is True
        assert result["title"] == "Cached Title"
        assert result["extractor"] == "tavily"

        mock_local.extract.assert_not_called()
