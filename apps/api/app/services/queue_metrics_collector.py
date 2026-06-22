"""Service to collect Celery queue and worker health metrics periodically."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.metrics import newsiq_queue_depth
from app.models.observability_models import QueueMetricsModel
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def collect_queue_metrics() -> None:
    """Query Redis and Celery control plane to snapshot queue and worker health.

    Updates the Prometheus gauge and records the snapshot in the Postgres database.
    """
    # 1. Query Redis directly for waiting jobs
    try:
        r = aioredis.from_url(settings.CELERY_BROKER_URL)
        waiting = await r.llen("celery")
        await r.aclose()
    except Exception as e:
        logger.warning(f"Failed to query Redis broker: {e}")
        waiting = 0

    # 2. Query Celery control inspect in executor (since it blocks on networking)
    def inspect_celery() -> tuple[int, int]:
        try:
            inspect = celery_app.control.inspect()
            # control.inspect methods can block or return None if workers are unresponsive
            stats = inspect.stats() or {}
            active = inspect.active() or {}

            worker_count = len(stats)
            active_count = sum(len(tasks) for tasks in active.values())
            return worker_count, active_count
        except Exception as err:
            logger.warning(f"Failed to inspect Celery control plane: {err}")
            return 0, 0

    loop = asyncio.get_running_loop()
    worker_count, active_count = await loop.run_in_executor(None, inspect_celery)

    # 3. Update Prometheus gauge
    newsiq_queue_depth.labels(queue_name="celery").set(waiting + active_count)

    # 4. Save to database
    try:
        async with async_session_factory() as session:
            metrics_record = QueueMetricsModel(
                queue_name="celery",
                waiting_jobs=waiting,
                active_jobs=active_count,
                worker_count=worker_count,
                captured_at=datetime.now(UTC).replace(tzinfo=None),
            )
            session.add(metrics_record)
            await session.commit()
            logger.debug(
                "Queue metrics snapshot persisted.",
                extra={
                    "waiting": waiting,
                    "active": active_count,
                    "workers": worker_count,
                },
            )
    except Exception as e:
        logger.error(f"Failed to persist queue metrics snapshot: {e}")
