"""Celery worker configuration and application initialization."""

import logging

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery instance
celery_app = Celery(
    "newsiq_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configuration settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Configure auto-discovery of tasks in the workers/tasks packages
    imports=[
        "app.workers.tasks",
        "app.tasks.cleanup_sessions",
        "app.workers.digest_tasks",
    ],
)

# Configure Periodic Tasks (Celery Beat Schedule)
celery_app.conf.beat_schedule = {
    # RSS ingestion — runs every 5 minutes across all active sources
    "ingest-rss-news-every-5-minutes": {
        "task": "app.workers.tasks.ingest_news_task",
        "schedule": crontab(minute="*/5"),
    },
    # GNews API ingestion — runs every 30 minutes (rate-limit guard handles sub-interval skips)
    "ingest-gnews-every-30-minutes": {
        "task": "app.workers.tasks.ingest_gnews_task",
        "schedule": crontab(minute="*/30"),
    },
    # Batch clustering — runs every 10 minutes to group new articles into stories
    "cluster-news-every-10-minutes": {
        "task": "app.workers.tasks.cluster_news_task",
        "schedule": crontab(minute="*/10"),
    },
    # Event extraction — runs every 10 minutes to extract structured events from articles
    "extract-events-every-10-minutes": {
        "task": "app.workers.tasks.extract_events_task",
        "schedule": crontab(minute="*/10"),
    },
    # Session cleanup — runs daily at midnight UTC
    "cleanup-expired-sessions-daily": {
        "task": "app.tasks.cleanup_sessions.cleanup_expired_sessions_task",
        "schedule": crontab(hour="0", minute="0"),
    },
    # Hourly digest delivery
    "process-hourly-digests-hourly": {
        "task": "app.workers.digest_tasks.process_hourly_digests_task",
        "schedule": crontab(minute="0"),
    },
    # Collect queue and worker metrics every minute
    "collect-queue-metrics-every-minute": {
        "task": "app.workers.tasks.collect_queue_metrics_task",
        "schedule": crontab(minute="*"),
    },
}

