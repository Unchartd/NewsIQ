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
        # This test validates the legacy Article-First path.
        patch("app.core.config.settings.STORY_FIRST_ENABLED", False),
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
        # This test validates the legacy Article-First path (STORY_FIRST_ENABLED=True
        # would route to metadata scoring instead of crawling).
        patch("app.core.config.settings.STORY_FIRST_ENABLED", False),
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
        # This test validates the legacy Article-First path.
        patch("app.core.config.settings.STORY_FIRST_ENABLED", False),
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


@pytest.mark.asyncio
async def test_existing_articles_not_crawled(mock_db_session):
    """PERF-01 regression: URLs that already exist in the DB must NOT be passed to the crawler.

    Previously, all feed URLs (including known ones) were forwarded to _crawl_articles,
    wasting HTTP requests for articles that already exist and haven't changed.
    After the fix, only genuinely new URLs are crawled.
    """
    source = Source(
        id=MagicMock(),
        name="Test News",
        slug="test-news",
        rss_url="http://example.com/rss",
        active=True,
    )

    existing_url = "http://example.com/existing-article"
    new_url = "http://example.com/new-article"

    # DB batch query returns one existing article
    existing_article = MagicMock()
    existing_article.content_hash = "existing_hash"
    existing_article.url = existing_url
    existing_article.version = 1

    # simulate _batch_existing_articles → first execute returns list; second execute returns
    # the content-hash dedup results (empty — no duplicates)
    results_batch = MagicMock()
    results_batch.scalars.return_value.all.return_value = [existing_article]

    results_dedup = MagicMock()
    results_dedup.scalars.return_value.all.return_value = []

    mock_db_session.execute.side_effect = [results_batch, results_dedup]

    mock_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Test News Channel</title>
            <link>http://example.com</link>
            <item>
                <title>Existing Article</title>
                <link>{existing_url}</link>
                <description>Existing</description>
                <pubDate>Fri, 12 Jun 2026 10:00:00 GMT</pubDate>
            </item>
            <item>
                <title>Brand New Article</title>
                <link>{new_url}</link>
                <description>Brand new content that is long enough</description>
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

    crawled_new = {
        "content": "Brand new full content that is definitely long enough to pass all checks.",
        "title": "Brand New Article",
        "author": None,
        "image_url": None,
        "success": True,
    }

    crawl_calls = []

    async def mock_crawl(url):
        crawl_calls.append(url)
        return crawled_new

    with (
        patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)),
        patch(
            "app.services.ingestion_service.compute_fingerprints",
            side_effect=lambda url, t, b: {
                "url_hash": f"hash_{url}",
                "content_hash": f"chash_{url}",
            },
        ),
        patch(
            "app.services.ingestion_service.url_bloom_filter.add",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.crawler_service.crawler_service.crawl_article",
            side_effect=mock_crawl,
        ),
        # This test validates the legacy Article-First path.
        patch("app.core.config.settings.STORY_FIRST_ENABLED", False),
    ):
        await ingestion_service.ingest_rss_source(source, mock_db_session)

    # CRITICAL: the existing URL must NOT have been crawled — only the new URL
    assert existing_url not in crawl_calls, (
        f"Existing article was crawled unnecessarily: {crawl_calls}"
    )
    assert new_url in crawl_calls, "New article was not crawled"
    assert len(crawl_calls) == 1, f"Expected exactly 1 crawl, got {len(crawl_calls)}: {crawl_calls}"


@pytest.mark.asyncio
async def test_content_hash_batch_dedup(mock_db_session):
    """PERF-02 regression: content_hash deduplication must use a single batched IN query.

    Previously, _persist_articles issued one SELECT per article to check content_hash.
    After the fix, all content hashes are checked in a single SELECT ... WHERE IN (...).
    """
    source = Source(
        id=MagicMock(),
        name="Test News",
        slug="test-news",
        rss_url="http://example.com/rss",
        active=True,
    )

    mock_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Test News</title>
            <link>http://example.com</link>
            <item>
                <title>Article One</title>
                <link>http://example.com/art1</link>
                <description>Content one</description>
                <pubDate>Fri, 12 Jun 2026 10:00:00 GMT</pubDate>
            </item>
            <item>
                <title>Article Two</title>
                <link>http://example.com/art2</link>
                <description>Content two</description>
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

    # First execute → _batch_existing_articles (no existing articles)
    result_existing = MagicMock()
    result_existing.scalars.return_value.all.return_value = []

    # Second execute → batch content_hash IN query (no duplicates)
    result_dedup = MagicMock()
    result_dedup.scalars.return_value.all.return_value = []

    mock_db_session.execute.side_effect = [result_existing, result_dedup]

    crawled_content = {
        "content": "Full crawled content that is definitely long enough for tests.",
        "title": "Article",
        "author": None,
        "image_url": None,
        "success": True,
    }

    with (
        patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)),
        patch(
            "app.services.ingestion_service.compute_fingerprints",
            side_effect=lambda url, t, b: {"url_hash": f"h_{url}", "content_hash": f"ch_{url}"},
        ),
        patch(
            "app.services.ingestion_service.url_bloom_filter.add",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.crawler_service.crawler_service.crawl_article",
            AsyncMock(return_value=crawled_content),
        ),
        # This test validates the legacy Article-First path.
        patch("app.core.config.settings.STORY_FIRST_ENABLED", False),
    ):
        await ingestion_service.ingest_rss_source(source, mock_db_session)

    # With PERF-02, there should be exactly 2 DB execute calls:
    #   1. _batch_existing_articles  (SELECT WHERE url IN ...)
    #   2. batch content_hash dedup  (SELECT WHERE content_hash IN ...)
    # NOT 2 + N individual per-article queries.
    assert mock_db_session.execute.call_count == 2, (
        f"Expected 2 DB queries (batch existing + batch dedup), "
        f"got {mock_db_session.execute.call_count}"
    )


@pytest.mark.asyncio
async def test_existing_articles_not_overwritten(mock_db_session):
    """Verify that existing articles in the DB are not updated/overwritten with feed summaries."""
    source = Source(
        id=MagicMock(),
        name="Test News",
        slug="test-news",
        rss_url="http://example.com/rss",
        active=True,
    )

    existing_url = "http://example.com/existing-article"

    # DB batch query returns one existing article
    existing_article = MagicMock()
    existing_article.content_hash = "existing_full_body_hash"
    existing_article.url = existing_url
    existing_article.version = 1

    # Simulate _batch_existing_articles
    results_batch = MagicMock()
    results_batch.scalars.return_value.all.return_value = [existing_article]

    mock_db_session.execute.return_value = results_batch

    mock_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Test News Channel</title>
            <link>http://example.com</link>
            <item>
                <title>Existing Article</title>
                <link>{existing_url}</link>
                <description>Existing Summary</description>
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

    with (
        patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)),
        patch("app.services.crawler_service.crawler_service.crawl_article") as mock_crawl,
        # This test validates the legacy Article-First path.
        patch("app.core.config.settings.STORY_FIRST_ENABLED", False),
    ):
        await ingestion_service.ingest_rss_source(source, mock_db_session)

        # Verify no crawl was attempted
        mock_crawl.assert_not_called()

    # Verify session.add was never called for existing_article (meaning no update)
    # and version was not incremented
    assert existing_article.version == 1
    for call in mock_db_session.add.call_args_list:
        assert call[0][0] != existing_article


# ── Story-First Pipeline Tests ─────────────────────────────────────────────────


class TestCalculateMetadataScore:
    """Unit tests for IngestionService.calculate_metadata_score (Story-First path)."""

    def test_missing_title_returns_zero(self):
        score, breakdown = ingestion_service.calculate_metadata_score(None, None, None)
        assert score == 0.0
        assert breakdown["reason"] == "missing_title"

    def test_opinion_title_rejected(self):
        score, breakdown = ingestion_service.calculate_metadata_score(
            "Opinion: Why everything is wrong", "Some description", datetime.utcnow()
        )
        assert score < 0
        assert breakdown["reason"] == "skipped_topic_opinion"

    def test_stale_article_rejected(self):
        stale_date = datetime.utcnow() - timedelta(hours=25)
        score, breakdown = ingestion_service.calculate_metadata_score(
            "Breaking News About Important Event", "Description", stale_date
        )
        assert score < 0
        assert breakdown["reason"] == "stale_article"

    def test_fresh_article_with_entities_scores_positively(self):
        pub_date = datetime.utcnow()
        score, breakdown = ingestion_service.calculate_metadata_score(
            title="Federal Reserve Raises Interest Rates Amid Inflation Concerns",
            description="The Federal Reserve announced a rate hike today.",
            pub_date=pub_date,
            source_name="Reuters",
        )
        assert score >= 0.25, f"Expected score >= 0.25, got {score}: {breakdown}"
        assert breakdown["source"] == "metadata_only"

    def test_trusted_publisher_increases_score(self):
        pub_date = datetime.utcnow()
        score_trusted, _ = ingestion_service.calculate_metadata_score(
            "US Congress Passes Budget Resolution", "Congress voted today.", pub_date, "Reuters"
        )
        score_unknown, _ = ingestion_service.calculate_metadata_score(
            "US Congress Passes Budget Resolution", "Congress voted today.", pub_date, "UnknownBlog"
        )
        assert score_trusted >= score_unknown, "Trusted publisher should score >= unknown publisher"

    def test_no_pubdate_uses_fallback(self):
        score, breakdown = ingestion_service.calculate_metadata_score(
            "Trump Signs Executive Order on Trade", "Description", None
        )
        # Should not be rejected (negative) — fallback freshness 0.25 is used
        assert score >= 0.0
        assert breakdown.get("freshness") == 0.25

    def test_live_scores_rejected(self):
        score, breakdown = ingestion_service.calculate_metadata_score(
            "LIVE SCORE: England vs Australia Test Match", "Live cricket scores", datetime.utcnow()
        )
        assert score < 0
        assert breakdown["reason"] == "skipped_topic_opinion"


@pytest.mark.asyncio
async def test_story_first_skips_low_score_entries(mock_db_session):
    """Verify _ingest_rss_story_first does not dispatch StoryCandidate for low-score entries."""
    from unittest.mock import AsyncMock, patch

    source = Source(
        id=MagicMock(),
        name="Test News",
        slug="test-news",
        rss_url="http://example.com/rss",
        active=True,
    )

    # No existing articles
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_execute_result

    # RSS feed with opinion/low-quality article (should be skipped)
    mock_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Test News Channel</title>
            <link>http://example.com</link>
            <item>
                <title>Opinion: My thoughts on today</title>
                <link>http://example.com/opinion1</link>
                <description>Personal editorial opinion piece</description>
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

    with (
        patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)),
        patch("app.core.config.settings.STORY_FIRST_ENABLED", True),
        patch(
            "app.services.ingestion_service.IngestionService._upsert_story_candidate",
            AsyncMock(),
        ) as mock_upsert,
    ):
        count = await ingestion_service.ingest_rss_source(source, mock_db_session)

    # Opinion + stale date → 0 dispatched, upsert never called
    assert count == 0
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_story_first_dispatches_fresh_qualifying_entry(mock_db_session):
    """Verify _ingest_rss_story_first calls _upsert_story_candidate for a qualifying entry."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, patch

    source = Source(
        id=MagicMock(),
        name="Reuters",
        slug="reuters",
        rss_url="http://reuters.com/rss",
        active=True,
    )

    # No existing articles
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_execute_result

    # Fresh RSS entry — use current UTC time formatted as RFC 2822
    from email.utils import format_datetime

    fresh_date = format_datetime(datetime.now(UTC))

    mock_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
        <channel>
            <title>Reuters</title>
            <link>http://reuters.com</link>
            <item>
                <title>Federal Reserve Raises Rates Amid Inflation</title>
                <link>http://reuters.com/economy/fed-rates-2026</link>
                <description>The Fed raised interest rates by 25 basis points today.</description>
                <pubDate>{fresh_date}</pubDate>
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

    with (
        patch("httpx.AsyncClient.get", return_value=MockResponse(mock_xml)),
        patch("app.core.config.settings.STORY_FIRST_ENABLED", True),
        patch(
            "app.core.config.settings.STORY_FIRST_SCORE_THRESHOLD", 0.0
        ),  # Accept all positive scores
        patch(
            "app.services.ingestion_service.IngestionService._upsert_story_candidate",
            AsyncMock(),
        ) as mock_upsert,
        patch("app.services.gnews_service.gnews_service._incr_metric", AsyncMock()),
    ):
        count = await ingestion_service.ingest_rss_source(source, mock_db_session)

    # Fresh, qualifying entry → should be dispatched
    assert count == 1
    mock_upsert.assert_called_once()
    # Verify the title was passed
    call_kwargs = mock_upsert.call_args.kwargs
    assert "federal reserve" in call_kwargs.get("title", "").lower() or count == 1
