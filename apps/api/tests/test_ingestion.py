"""Unit tests for the news ingestion and embedding services."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.models import Source
from app.services.ingestion_service import ingestion_service


def test_clean_html():
    """Verify HTML tags are stripped from strings correctly."""
    dirty_html = "<p>Hello <b>World</b>! Check out <a href='https://example.com'>this link</a>.</p>"
    cleaned = ingestion_service.clean_html(dirty_html)
    assert "Hello" in cleaned
    assert "World" in cleaned
    assert "Check out this link" in cleaned
    assert "<p>" not in cleaned


def test_clean_html_none():
    """Verify None values are handled gracefully."""
    assert ingestion_service.clean_html(None) == ""


@pytest.mark.asyncio
async def test_ingest_rss_source_no_new(mock_db_session):
    """Verify that ingestion service handles duplicate URLs (returns 0 new)."""
    # Mocking active source
    source = Source(
        id=MagicMock(),
        name="Test News",
        slug="test-news",
        rss_url="http://example.com/rss",
        active=True,
    )

    # Mock DB query to return an existing article (simulating a duplicate URL)
    existing_article = MagicMock()
    existing_article.content_hash = "hash1"
    existing_article.url = "http://example.com/article1"
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [existing_article]
    mock_db_session.execute.return_value = mock_execute_result

    # Mock RSS Feed XML
    mock_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Test News Channel</title>
            <link>http://example.com</link>
            <item>
                <title>Duplicate News Article</title>
                <link>http://example.com/article1</link>
                <description>Some description</description>
                <pubDate>Fri, 12 Jun 2026 10:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>
    """

    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self):
            pass

    from unittest.mock import AsyncMock

    # Patch httpx.AsyncClient.get to return our mock XML, bloom filter to return True, and compute_fingerprints to match
    with (
        patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)),
        patch(
            "app.services.ingestion_service.url_bloom_filter.exists", AsyncMock(return_value=True)
        ),
        patch(
            "app.services.ingestion_service.compute_fingerprints",
            return_value={"url_hash": "hash1", "content_hash": "hash1"},
        ),
    ):
        count = await ingestion_service.ingest_rss_source(source, mock_db_session)
        assert count == 0


@pytest.mark.asyncio
async def test_ingest_rss_with_crawler_success(mock_db_session):
    """Verify that RSS ingestion crawls and integrates full-text content when available."""
    source = Source(
        id=MagicMock(),
        name="Test News",
        slug="test-news",
        rss_url="http://example.com/rss",
        active=True,
    )

    # Mock DB query to return None (simulating a new URL)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_result

    # Mock RSS Feed XML
    mock_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Test News Channel</title>
            <link>http://example.com</link>
            <item>
                <title>New News Article</title>
                <link>http://example.com/article2</link>
                <description>Feed Summary</description>
                <pubDate>Fri, 12 Jun 2026 10:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>
    """

    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self):
            pass

    # Mock crawled data
    crawled_mock = {
        "content": "This is the crawled full text of the article from the remote site. It is much longer and more detailed than the feed summary.",
        "author": "John Doe",
        "image_url": "http://example.com/image.jpg",
        "title": "Crawled Article Title",
        "extractor": "newspaper4k",
    }

    # Patch both the HTTP client get and crawler_service.crawl_article
    with (
        patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)),
        patch(
            "app.services.crawler_service.crawler_service.crawl_article", return_value=crawled_mock
        ),
    ):
        count = await ingestion_service.ingest_rss_source(source, mock_db_session)
        assert count == 1

        # Verify that article was added to session
        added_objs = [call[0][0] for call in mock_db_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert article.content == crawled_mock["content"]
        assert article.author == "John Doe"
        assert article.image_url == "http://example.com/image.jpg"


@pytest.mark.asyncio
async def test_ingest_rss_with_crawler_failure_fallback(mock_db_session):
    """Verify that RSS ingestion falls back to RSS summary when crawler fails."""
    source = Source(
        id=MagicMock(),
        name="Test News",
        slug="test-news",
        rss_url="http://example.com/rss",
        active=True,
    )

    # Mock DB query to return None (simulating a new URL)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_result

    # Mock RSS Feed XML
    mock_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Test News Channel</title>
            <link>http://example.com</link>
            <item>
                <title>Fallback News Article</title>
                <link>http://example.com/article3</link>
                <description>Feed Summary Content</description>
                <pubDate>Fri, 12 Jun 2026 10:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>
    """

    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self):
            pass

    # Patch both the HTTP client get and crawler_service.crawl_article (returning None)
    with (
        patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)),
        patch("app.services.crawler_service.crawler_service.crawl_article", return_value=None),
    ):
        count = await ingestion_service.ingest_rss_source(source, mock_db_session)
        assert count == 1

        # Verify that article was added to session and has feed summary content
        added_objs = [call[0][0] for call in mock_db_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert article.content == "Feed Summary Content"
