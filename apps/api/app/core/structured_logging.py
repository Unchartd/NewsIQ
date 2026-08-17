"""Structured logging for NewsIQ using structlog.

Replaces the basic JSONFormatter with a production-grade structured logging
pipeline that automatically binds trace context (run_id, trace_id, span_id,
stage, story_id, article_id) to every log entry.

Output format: JSON lines compatible with Datadog, Grafana Loki, ELK stack.

Usage:
    import structlog
    logger = structlog.get_logger(__name__)

    # Context is automatically injected from trace.py contextvars
    logger.info("article_embedded", article_id=str(art.id), latency_ms=42.5)

    # Output:
    # {"timestamp": "2026-06-20T14:30:00Z", "level": "info", "logger": "app.services.embedding_service",
    #  "event": "article_embedded", "article_id": "abc-123", "latency_ms": 42.5,
    #  "trace_id": "...", "run_id": "...", "stage": "embedding"}
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any

import structlog
from structlog.types import EventDict


def _add_trace_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Structlog processor that injects trace context from contextvars."""
    from app.core.trace import (
        article_id_ctx,
        run_id_ctx,
        span_id_ctx,
        stage_ctx,
        story_id_ctx,
        trace_id_ctx,
    )

    # Only add non-empty values to keep logs clean
    ctx_vars = {
        "trace_id": trace_id_ctx.get(""),
        "run_id": run_id_ctx.get(""),
        "span_id": span_id_ctx.get(""),
        "stage": stage_ctx.get(""),
        "story_id": story_id_ctx.get(""),
        "article_id": article_id_ctx.get(""),
    }
    for key, value in ctx_vars.items():
        if value and key not in event_dict:
            event_dict[key] = value

    return event_dict


def _add_request_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Inject the FastAPI request_id from the existing context var."""
    from app.core.logging import request_id_ctx_var

    request_id = request_id_ctx_var.get("")
    if request_id:
        event_dict.setdefault("request_id", request_id)
    return event_dict


def _add_timestamp(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add ISO 8601 UTC timestamp."""
    event_dict["timestamp"] = datetime.now(UTC).isoformat()
    return event_dict


def _add_service_info(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add service metadata."""
    event_dict.setdefault("service", "newsiq-api")
    return event_dict


# Stage logs are written to Redis from a structlog processor, which runs inline
# on every log call — including inside async worker code.
#
# The previous implementation called redis.from_url() per log line: a fresh
# connection, never pooled and never closed, followed by three separate blocking
# round trips (rpush, expire, publish). At 8,412 stage runs a day this was the
# single largest avoidable cost in the telemetry path, and the whole body was
# wrapped in `except Exception: pass`, so a broken Redis was invisible.
#
# One pooled client, one pipelined round trip, and failures that are reported.
_LOG_TTL_SECONDS = 86_400
# A stage that logs in a loop would otherwise grow an unbounded Redis list; the
# viewer only ever renders the tail.
_LOG_MAX_LINES = 2_000

_redis_log_client: Any = None
_redis_log_failures = 0

_STANDARD_KEYS = frozenset(
    {
        "timestamp",
        "level",
        "event",
        "run_id",
        "trace_id",
        "span_id",
        "stage",
        "story_id",
        "article_id",
        "service",
    }
)


def _get_log_redis() -> Any:
    """Return the shared, pooled Redis client used for stage logs."""
    global _redis_log_client
    if _redis_log_client is None:
        import redis

        from app.core.config import settings

        # A small pool: this is a side channel, not the application's data path,
        # and it must never starve the pools that carry real work.
        _redis_log_client = redis.from_url(
            settings.REDIS_URL,
            max_connections=8,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            retry_on_timeout=False,
        )
    return _redis_log_client


def _report_log_failure(exc: Exception) -> None:
    """Surface Redis logging failures without recursing through structlog."""
    global _redis_log_failures
    _redis_log_failures += 1
    # Report the first failure, then every 500th, using the stdlib logger
    # directly — going through structlog here would re-enter this processor.
    if _redis_log_failures == 1 or _redis_log_failures % 500 == 0:
        logging.getLogger(__name__).warning(
            "Stage log persistence to Redis failed (%d total): %s. "
            "Stage logs will be missing from the dashboard.",
            _redis_log_failures,
            exc,
        )


def snapshot_stage_logs(run_id: str, stage: str, limit: int = 200) -> list[str]:
    """Return the tail of a stage's logs so they can outlive Redis.

    Stage logs live only in Redis under a 24-hour TTL, and there is no durable
    store — `error_logs` exists as a table and holds zero rows. So a run that
    failed yesterday has no logs today, which is exactly when they are wanted.

    Callers snapshot this into the stage's metadata on failure. Bounded, because
    a failing stage in a retry loop can produce a great deal of output and this
    ends up in a JSONB column.
    """
    if not (run_id and stage):
        return []
    try:
        raw = _get_log_redis().lrange(f"newsiq:logs:{run_id}:{stage}", -limit, -1)
    except Exception as exc:
        _report_log_failure(exc)
        return []
    return [
        line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line) for line in raw
    ]


def _store_and_publish_log(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Persist and stream logs emitted inside a StageSpan.

    Only fires when both run_id and stage are bound, i.e. inside a stage span —
    which is why a log written outside one never reaches the dashboard.
    """
    run_id = event_dict.get("run_id")
    stage = event_dict.get("stage")
    if not (run_id and stage):
        return event_dict

    try:
        import json

        timestamp = event_dict.get("timestamp", datetime.now(UTC).isoformat())
        level = str(event_dict.get("level", "info")).upper()
        event = event_dict.get("event", "")

        extra = {
            k: v for k, v in event_dict.items() if k not in _STANDARD_KEYS and not k.startswith("_")
        }
        extra_str = f" {json.dumps(extra, default=str)}" if extra else ""
        log_line = f"{timestamp} [{level}] {event}{extra_str}"

        redis_key = f"newsiq:logs:{run_id}:{stage}"
        redis_channel = f"{redis_key}:stream"

        # One round trip instead of three, on a reused connection.
        pipe = _get_log_redis().pipeline(transaction=False)
        pipe.rpush(redis_key, log_line)
        pipe.ltrim(redis_key, -_LOG_MAX_LINES, -1)
        pipe.expire(redis_key, _LOG_TTL_SECONDS)
        pipe.publish(redis_channel, log_line)
        pipe.execute()
    except Exception as exc:
        # Logging must never break the operation being logged.
        _report_log_failure(exc)

    return event_dict


def setup_structlog(debug: bool = False) -> None:
    """Initialize structlog with the full processing pipeline.

    This configures both structlog loggers and stdlib loggers to output
    structured JSON. All existing stdlib logger.info() calls will
    automatically get trace context injected.

    Args:
        debug: If True, use console renderer for development.
               If False, use JSON renderer for production.
    """
    # Shared processors for both structlog and stdlib
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_timestamp,
        _add_trace_context,
        _add_request_id,
        _add_service_info,
        _store_and_publish_log,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    renderer: Any
    if debug:
        # Development: colored console output
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )
    else:
        # Production: JSON output for log aggregators
        renderer = structlog.processors.JSONRenderer()

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging to use structlog's formatting
    # This ensures existing logger.info() calls get structured output
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            _add_timestamp,
            _add_trace_context,
            _add_request_id,
            _add_service_info,
            _store_and_publish_log,
            structlog.stdlib.ExtraAdder(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.format_exc_info,
        ],
    )

    # Replace all stdlib handlers with structlog-aware handler
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Silence chatty third-party loggers
    for noisy_logger in (
        "httpx",
        "httpcore",
        "uvicorn.access",
        "celery.utils.log",
        "asyncio",
        "sqlalchemy.engine",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger instance.

    This is the preferred way to create loggers in the observability platform.
    Returns a logger that automatically includes trace context.

    Usage:
        from app.core.structured_logging import get_logger
        logger = get_logger(__name__)
        logger.info("processing_article", article_id="abc", latency_ms=42)
    """
    return structlog.get_logger(name)
