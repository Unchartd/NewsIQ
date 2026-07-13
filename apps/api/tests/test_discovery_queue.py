import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DiscoveryTask, DiscoveryTaskState, CrawlTask, CrawlTaskState, Article
from app.workers.tasks import discovery_search_task, discovery_crawl_task, _check_discovery_task_completion


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
        created_at=datetime.now(UTC).replace(tzinfo=None)
    )
    
    mock_article = Article(
        id=article_id,
        title="Apple AI chips WWDC",
        published_at=datetime.now(UTC).replace(tzinfo=None)
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
    mock_cache.get.return_value = None # Budget not exceeded
    mock_cache.set.return_value = True # Lock acquired
    
    mock_provider = AsyncMock()
    mock_provider.search.return_value = ["https://reuters.com/news1", "https://bbc.com/news2"]
    
    mock_rank = MagicMock(return_value=["https://reuters.com/news1", "https://bbc.com/news2"])
    
    with (
        patch("app.workers.tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.services.cache_service.cache_service", mock_cache),
        patch("app.ingestion.get_discovery_provider", return_value=mock_provider),
        patch("app.services.gnews_service.gnews_service.rank_and_filter_search_results", mock_rank),
        patch("app.workers.tasks.discovery_crawl_task.delay") as mock_delay
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
        created_at=datetime.now(UTC).replace(tzinfo=None)
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
    mock_cache.get.return_value = 99999 # Exceed budget
    
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
        created_at=datetime.now(UTC).replace(tzinfo=None)
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
    mock_bloom.exists.return_value = True # Hash exists
    
    with (
        patch("app.workers.tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.services.ingestion_service.url_bloom_filter", mock_bloom),
        patch("app.workers.tasks._check_discovery_task_completion", AsyncMock()) as mock_completion
    ):
        discovery_crawl_task(str(crawl_task_id))
        assert mock_crawl_task.status == CrawlTaskState.SUCCESS
        assert mock_crawl_task.outcome == "BLOOM_SKIP"
        assert mock_completion.call_count == 1
