"""Celery worker configuration and application initialization.

TLS / Upstash Notes:
  - Upstash Redis requires TLS (rediss:// scheme).
  - When CELERY_BROKER_URL starts with "rediss://", broker_use_ssl is set
    automatically so Celery connects over TLS without certificate verification
    (Upstash uses a managed cert — no client cert needed).
  - Three separate Upstash instances are required because Upstash does not
    support multiple Redis DB indices (/0, /1, /2):
      REDIS_URL              → app cache  (not used by Celery directly)
      CELERY_BROKER_URL      → task queue broker
      CELERY_RESULT_BACKEND  → task result storage

Migration to self-hosted Redis:
  Change the three env vars to your Redis host. No code changes needed.
"""

import logging

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_broker_transport_options(url: str) -> dict:
    """Build Celery broker_transport_options for TLS when using rediss://."""
    if url.startswith("rediss://"):
        return {
            "visibility_timeout": 3600,
            "fanout_prefix": True,
            "fanout_patterns": True,
        }
    return {}


def _build_broker_use_ssl(url: str) -> dict | None:
    """Return broker_use_ssl config for Upstash/TLS Redis connections.

    ssl_cert_reqs=None disables certificate hostname verification.
    Upstash manages its own certificate — no client cert is needed.
    """
    if url.startswith("rediss://"):
        return {
            "ssl_cert_reqs": None,
        }
    return None


# ── Celery application ────────────────────────────────────────────────────────
celery_app = Celery(
    "newsiq_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# ── Base configuration ────────────────────────────────────────────────────────
_conf: dict = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "broker_transport_options": _build_broker_transport_options(settings.CELERY_BROKER_URL),
    # Auto-discover tasks
    "imports": [
        "app.workers.tasks",
        "app.tasks.cleanup_sessions",
        "app.workers.digest_tasks",
    ],
}

# Attach TLS config if broker uses rediss://
_broker_ssl = _build_broker_use_ssl(settings.CELERY_BROKER_URL)
if _broker_ssl:
    _conf["broker_use_ssl"] = _broker_ssl

# Attach TLS config for result backend if it uses rediss://
_backend_ssl = _build_broker_use_ssl(settings.CELERY_RESULT_BACKEND)
if _backend_ssl:
    _conf["redis_backend_use_ssl"] = _backend_ssl

celery_app.conf.update(_conf)

# ── Periodic Tasks (Celery Beat Schedule) ────────────────────────────────────
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
    # Evaluate story lifecycles
    "evaluate-story-lifecycles-every-15-minutes": {
        "task": "app.workers.tasks.evaluate_story_lifecycles_task",
        "schedule": crontab(minute="*/15"),
    },
    # Collect queue and worker metrics every minute
    "collect-queue-metrics-every-minute": {
        "task": "app.workers.tasks.collect_queue_metrics_task",
        "schedule": crontab(minute="*"),
    },
    # Aggregate pipeline dashboard metrics every minute
    "aggregate-pipeline-metrics-every-minute": {
        "task": "app.workers.tasks.aggregate_pipeline_metrics_task",
        "schedule": crontab(minute="*"),
    },
}


from celery.signals import setup_logging  # noqa: E402


@setup_logging.connect
def on_setup_logging(*args, **kwargs):
    from app.core.logging import setup_logging as _setup

    _setup(settings.DEBUG)
