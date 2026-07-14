import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Article, CrawlTask, CrawlTaskState, DiscoveryTask, DiscoveryTaskState
from app.workers.tasks import (
    discovery_crawl_task,
    discovery_search_task,
)


def test_discovery_search_task_success():
    """Verify that discovery_search_task fetches, ranks, and creates CrawlTasks in PENDING state."""
    task_id = uuid.uuid4()
    article_id = uuid.uuid4()

    mock_task = DiscoveryTask(
        id=task_id,
        article_id=article_id,
        query="Apple AI chips WWDC",
        provider="google_rss",
        status=DiscoveryTaskState.PENDING,
        retry_count=0,
        idempotency_key="google_rss:hash:2026-07-14",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_article = Article(
        id=article_id,
        title="Apple AI chips WWDC",
        published_at=datetime.now(UTC).replace(tzinfo=None),
    )

    # Mock database session execution
    mock_db_session = MagicMock(spec=AsyncSession)
    mock_db_session.execute = AsyncMock()
    mock_db_session.commit = AsyncMock()
    mock_db_session.flush = AsyncMock()

    # Mocking task and article retrievals
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.side_effect = [mock_task, mock_article]
    mock_db_session.execute.return_value = mock_scalar

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db_session

    # Mocking dependencies
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None  # Budget not exceeded
    mock_cache.set.return_value = True  # Lock acquired

    mock_provider = AsyncMock()
    mock_provider.search.return_value = ["https://reuters.com/news1", "https://bbc.com/news2"]
    mock_provider.resolve_url = AsyncMock(side_effect=lambda url: url)

    mock_rank = MagicMock(return_value=["https://reuters.com/news1", "https://bbc.com/news2"])

    with (
        patch("app.workers.tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.services.cache_service.cache_service", mock_cache),
        patch("app.ingestion.get_discovery_provider", return_value=mock_provider),
        patch("app.services.gnews_service.gnews_service.rank_and_filter_search_results", mock_rank),
        patch("app.workers.tasks.discovery_crawl_task.delay") as mock_delay,
    ):
        discovery_search_task(str(task_id))

        # Verify status transitioned to CRAWLING
        assert mock_task.status == DiscoveryTaskState.CRAWLING
        assert mock_task.search_started_at is not None
        assert mock_task.search_completed_at is not None
        assert mock_delay.call_count == 2


def test_discovery_search_task_budget_exceeded():
    """Verify that task is expired if daily search budget is exceeded."""
    task_id = uuid.uuid4()

    mock_task = DiscoveryTask(
        id=task_id,
        query="Apple AI chips",
        provider="google_rss",
        status=DiscoveryTaskState.PENDING,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_db_session = MagicMock(spec=AsyncSession)
    mock_db_session.execute = AsyncMock()
    mock_db_session.commit = AsyncMock()

    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = mock_task
    mock_db_session.execute.return_value = mock_scalar

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db_session

    mock_cache = AsyncMock()
    mock_cache.get.return_value = 99999  # Exceed budget

    with (
        patch("app.workers.tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.services.cache_service.cache_service", mock_cache),
    ):
        discovery_search_task(str(task_id))
        assert mock_task.status == DiscoveryTaskState.EXPIRED
        assert mock_task.last_error == "Daily search budget exceeded"


def test_discovery_crawl_task_bloom_skip():
    """Verify that crawl task skips and marks outcome as BLOOM_SKIP when URL hash exists in Bloom filter."""
    crawl_task_id = uuid.uuid4()
    discovery_task_id = uuid.uuid4()

    mock_crawl_task = CrawlTask(
        id=crawl_task_id,
        discovery_task_id=discovery_task_id,
        url="https://reuters.com/news1",
        url_hash="some_hash",
        status=CrawlTaskState.PENDING,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_db_session = MagicMock(spec=AsyncSession)
    mock_db_session.execute = AsyncMock()
    mock_db_session.commit = AsyncMock()

    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = mock_crawl_task
    mock_db_session.execute.return_value = mock_scalar

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db_session

    mock_bloom = AsyncMock()
    mock_bloom.exists.return_value = True  # Hash exists

    with (
        patch("app.workers.tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.services.ingestion_service.url_bloom_filter", mock_bloom),
        patch("app.workers.tasks._check_discovery_task_completion", AsyncMock()) as mock_completion,
    ):
        discovery_crawl_task(str(crawl_task_id))
        assert mock_crawl_task.status == CrawlTaskState.SUCCESS
        assert mock_crawl_task.outcome == "BLOOM_SKIP"
        assert mock_completion.call_count == 1


def test_discovery_crawl_task_sets_url_hash_on_article():
    """BUG-01 regression: Article created by discovery_crawl_task must have url_hash set.

    Previously, discovered articles had url_hash=NULL, making them invisible to
    bloom_filter.rebuild() which queries WHERE url_hash IS NOT NULL.
    After the fix, crawl_task.url_hash is copied to the new Article.
    """
    crawl_task_id = uuid.uuid4()
    discovery_task_id = uuid.uuid4()
    expected_url_hash = "abc123definitelyahash"

    mock_crawl_task = CrawlTask(
        id=crawl_task_id,
        discovery_task_id=discovery_task_id,
        url="https://reuters.com/unique-article",
        url_hash=expected_url_hash,
        status=CrawlTaskState.PENDING,
        retry_count=0,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_db_session = MagicMock(spec=AsyncSession)
    mock_db_session.execute = AsyncMock()
    mock_db_session.commit = AsyncMock()
    mock_db_session.flush = AsyncMock()
    mock_db_session.add = MagicMock()
    nested_mock = AsyncMock()
    nested_mock.__aenter__ = AsyncMock(return_value=nested_mock)
    nested_mock.__aexit__ = AsyncMock(return_value=None)
    mock_db_session.begin_nested = MagicMock(return_value=nested_mock)

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db_session

    # No URL duplicate, no content duplicate → returns None both times
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.side_effect = [
        mock_crawl_task,  # CrawlTask lookup
        None,  # URL dup check
        None,  # Content hash dup check
    ]
    mock_db_session.execute.return_value = mock_scalar

    mock_bloom = AsyncMock()
    mock_bloom.exists.return_value = False  # Not in bloom filter — proceed with crawl
    mock_bloom.add = AsyncMock(return_value=True)

    crawled_data = {
        "success": True,
        "content": "A substantial article body from Reuters about a unique discovery story.",
        "title": "Reuters Unique Article",
        "author": "Jane Doe",
        "image_url": None,
        "published_at": datetime.now(UTC).replace(tzinfo=None),
        "diagnostics": {"failure_reason": None},
    }

    mock_source = MagicMock()
    mock_source.id = uuid.uuid4()

    added_articles = []

    def capture_add(obj):
        if isinstance(obj, Article):
            added_articles.append(obj)

    mock_db_session.add.side_effect = capture_add

    with (
        patch("app.workers.tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.services.ingestion_service.url_bloom_filter", mock_bloom),
        patch(
            "app.services.crawler_service.crawler_service.crawl_article",
            AsyncMock(return_value=crawled_data),
        ),
        patch(
            "app.services.gnews_service.gnews_service._resolve_source",
            AsyncMock(return_value=mock_source),
        ),
        patch("app.workers.tasks._check_discovery_task_completion", AsyncMock()),
        patch("app.workers.tasks.process_pending_embeddings_task.delay", MagicMock()),
    ):
        discovery_crawl_task(str(crawl_task_id))

    # The Article added to the session must carry url_hash from the CrawlTask
    assert len(added_articles) == 1, f"Expected 1 Article added, got {len(added_articles)}"
    persisted_article = added_articles[0]
    assert persisted_article.url_hash == expected_url_hash, (
        f"Article.url_hash was {persisted_article.url_hash!r}, "
        f"expected {expected_url_hash!r} from CrawlTask"
    )
    assert persisted_article.fingerprint_version == 1, (
        "Article.fingerprint_version must be set to 1"
    )
