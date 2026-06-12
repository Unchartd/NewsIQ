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
    # Configure auto-discovery of tasks in the workers package
    imports=["app.workers.tasks"],
)

# Configure Periodic Tasks (Celery Beat Schedule)
celery_app.conf.beat_schedule = {
    "ingest-news-every-5-minutes": {
        "task": "app.workers.tasks.ingest_news_task",
        "schedule": crontab(minute="*/5"),
    },
    "cluster-news-every-10-minutes": {
        "task": "app.workers.tasks.cluster_news_task",
        "schedule": crontab(minute="*/10"),
    },
}
