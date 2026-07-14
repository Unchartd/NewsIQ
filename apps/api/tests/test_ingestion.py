"""Unit tests for the news ingestion and embedding services."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

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


def test_normalize_headline():
    """Verify that IngestionService.normalize_headline cleans and normalizes title strings correctly."""
    # Test prefix stripping and publisher stripping
    h1 = "BREAKING: Apple unveils new AI chips - TechCrunch"
    assert ingestion_service.normalize_headline(h1) == "apple unveils new ai chips"

    # Test Unicode NFKC and punctuation/quotes
    h2 = "LIVE: Donald Trump’s Speech on Strait of Hormuz..."
    assert ingestion_service.normalize_headline(h2) == "donald trumps speech on strait of hormuz"

    # Test collapse spaces
    h3 = "  This   free   Mac   app  reveals the truth  "
    assert ingestion_service.normalize_headline(h3) == "this free mac app reveals the truth"


def test_should_prioritize_discovery():
    """Verify prioritization filters of IngestionService.should_prioritize_discovery."""
    # Valid candidate (fresh, long, multiple proper nouns, no opinion keywords)
    valid_title = "Siya Goyal Pune Fort FIR Matchmaking Investigation details"
    valid_content = (
        "This is a very long content string of more than three hundred characters to satisfy the minimum length filter requirement in the diagnostic pipeline test. "
        * 3
    )
    pub_now = datetime.utcnow()

    ok, reason = ingestion_service.should_prioritize_discovery(valid_title, valid_content, pub_now)
    assert ok is True
    assert reason == ""

    # Test stale (>24h)
    pub_old = datetime.utcnow() - timedelta(hours=25)
    ok, reason = ingestion_service.should_prioritize_discovery(valid_title, valid_content, pub_old)
    assert ok is False
    assert reason == "stale_article"

    # Test content too short
    ok, reason = ingestion_service.should_prioritize_discovery(
        valid_title, "Short content", pub_now
    )
    assert ok is False
    assert reason == "content_too_short"

    # Test opinion keywords
    opinion_title = "Opinion: Why the Siya Goyal Pune Fort FIR Matchmaking details are wrong"
    ok, reason = ingestion_service.should_prioritize_discovery(
        opinion_title, valid_content, pub_now
    )
    assert ok is False
    assert reason == "skipped_topic_opinion"

    # Test low entity count (no proper nouns)
    no_ent_title = "we are going to check how things work in the city"
    ok, reason = ingestion_service.should_prioritize_discovery(no_ent_title, valid_content, pub_now)
    assert ok is False
    assert reason == "low_entity_count"


@pytest.mark.asyncio
async def test_search_and_ingest_similar_articles_cache_hit(mock_db_session):
    """Verify search_and_ingest_similar_articles reuses cached URLs on Redis hit."""
    from app.services.gnews_service import gnews_service

    mock_redis = AsyncMock()
    # Mock cache hit for URL list
    mock_redis.get.return_value = '["http://example.com/url1", "http://example.com/url2"]'

    # Temporarily set redis client
    orig_redis = gnews_service._redis
    gnews_service._redis = mock_redis

    # Patch DB checks and crawl/Bloom filter
    with (
        patch(
            "app.services.ingestion_service.url_bloom_filter.exists", AsyncMock(return_value=True)
        ),
        patch("app.services.gnews_service.gnews_service._incr_metric", AsyncMock()) as mock_incr,
    ):
        meta = await gnews_service.search_and_ingest_similar_articles(
            title="Siya Goyal Pune Fort FIR Matchmaking Details", session=mock_db_session
        )
        assert meta["cache_hit"] is True
        assert meta["urls_found"] == 2
        mock_incr.assert_any_call("search_cache_hit")

    gnews_service._redis = orig_redis


def test_calculate_discovery_score_weighted():
    """Verify weighted calculation of discovery score including custom trusted publishers and linear decays."""
    from datetime import datetime

    from app.services.ingestion_service import ingestion_service

    # 1. Valid fresh, trusted publisher candidate
    title = "Siya Goyal Pune Fort FIR Matchmaking details"
    content = "This is a very long text to satisfy the content length filter" * 15  # ~900 chars
    pub_now = datetime.utcnow()

    score, breakdown = ingestion_service.calculate_discovery_score(
        title=title, content=content, pub_date=pub_now, source_name="Reuters"
    )

    assert score > 0.60
    assert breakdown["trust"] == 1.0  # Reuters is 1.0
    assert breakdown["entity_count"] >= 4

    # 2. Opinion article rejected
    score, breakdown = ingestion_service.calculate_discovery_score(
        title="Opinion: why this is wrong", content=content, pub_date=pub_now
    )
    assert score < 0
    assert breakdown["reason"] == "skipped_topic_opinion"


def test_rank_and_filter_search_results():
    """Verify ranking algorithm prioritizes trusted sources, time proximity, fuzzy title match, and enforces domain diversity."""
    from datetime import datetime

    from app.services.gnews_service import gnews_service

    original_title = "Siya Goyal Pune Fort FIR Matchmaking Details"
    original_pub = datetime.utcnow()

    raw_results = [
        # Candidate 1: Reuters (trusted), fresh, high similarity
        {
            "url": "https://reuters.com/article1",
            "title": "Siya Goyal Pune Fort FIR Matchmaking Details Out",
            "description": "Details about Pune Fort FIR case",
            "gnews_source_name": "Reuters",
            "published_at": original_pub,
        },
        # Candidate 2: Same domain as 1 (should be filtered out by diversity check)
        {
            "url": "https://reuters.com/article2",
            "title": "Reuters extra on Siya Goyal Pune Fort case",
            "description": "More info",
            "gnews_source_name": "Reuters",
            "published_at": original_pub,
        },
        # Candidate 3: Unknown source, but high fuzzy match
        {
            "url": "https://unknownblog.com/post",
            "title": "Siya Goyal Pune Fort FIR Matchmaking Details",
            "description": "Pune Fort FIR case",
            "gnews_source_name": "Unknown Blog",
            "published_at": original_pub,
        },
    ]

    filtered_urls = gnews_service.rank_and_filter_search_results(
        results=raw_results,
        original_title=original_title,
        original_pub_date=original_pub,
        max_results=2,
    )

    # Assertions
    assert len(filtered_urls) == 2
    assert "https://reuters.com/article1" in filtered_urls
    # https://reuters.com/article2 should be skipped due to domain duplication (same as article1)
    assert "https://reuters.com/article2" not in filtered_urls
    assert "https://unknownblog.com/post" in filtered_urls
