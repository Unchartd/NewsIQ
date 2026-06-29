"""Unit tests for the Celery queue metrics collector."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.queue_metrics_collector import collect_queue_metrics


@pytest.mark.asyncio
async def test_collect_queue_metrics(mock_db_session):
    """Verify that queue metrics collection queries Redis/Celery and saves to DB."""
    # 1. Setup mocks
    mock_redis = AsyncMock()
    mock_redis.llen.return_value = 5  # 5 jobs waiting in Redis
    mock_redis.aclose = AsyncMock()

    mock_celery_inspect = MagicMock()
    mock_celery_inspect.stats.return_value = {"worker1@localhost": {}}
    mock_celery_inspect.active.return_value = {"worker1@localhost": [1, 2]}  # 2 active jobs

    # 2. Patch connections
    with (
        patch("redis.asyncio.from_url", return_value=mock_redis) as mock_redis_from_url,
        patch(
            "app.workers.celery_app.celery_app.control.inspect", return_value=mock_celery_inspect
        ),
        patch("app.services.queue_metrics_collector.async_session_factory") as mock_session_factory,
        patch("app.services.queue_metrics_collector.newsiq_queue_depth") as mock_gauge,
    ):
        # Mock the session context manager
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_db_session
        mock_session_factory.return_value = mock_session_ctx

        # 3. Call the collector
        await collect_queue_metrics()

        # 4. Verify Redis and Celery inspectors were called
        mock_redis_from_url.assert_called_once()
        mock_redis.llen.assert_called_once_with("celery")
        mock_celery_inspect.stats.assert_called_once()
        mock_celery_inspect.active.assert_called_once()

        # 5. Verify Prometheus Gauge update
        # 5 waiting + 2 active = 7 total depth
        mock_gauge.labels.assert_called_once_with(queue_name="celery")
        mock_gauge.labels.return_value.set.assert_called_once_with(7)

        # 6. Verify database persistence
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Retrieve the inserted record
        metrics_record = mock_db_session.add.call_args[0][0]
        assert metrics_record.queue_name == "celery"
        assert metrics_record.waiting_jobs == 5
        assert metrics_record.active_jobs == 2
        assert metrics_record.worker_count == 1
