"""Sentry integration and utility functions for observability."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Literal

import sentry_sdk

from app.core.trace import get_trace_context

logger = logging.getLogger(__name__)


def before_send_handler(event: Any, hint: dict[str, Any]) -> Any | None:
    """Enrich Sentry error events with current pipeline trace context tags."""
    ctx = get_trace_context()
    tags = event.setdefault("tags", {})
    for key, val in ctx.items():
        if val:
            tags[key] = val
    return event


def before_send_transaction_handler(event: Any, hint: dict[str, Any]) -> Any | None:
    """Enrich Sentry transactions with current pipeline trace context tags."""
    ctx = get_trace_context()
    tags = event.setdefault("tags", {})
    for key, val in ctx.items():
        if val:
            tags[key] = val
    return event


def capture_pipeline_error(
    error: Exception,
    stage: str,
    severity: Literal["fatal", "critical", "error", "warning", "info", "debug"] = "error",
    extra_metadata: dict[str, Any] | None = None,
) -> None:
    """Capture a pipeline error with enriched trace context tags and extra metadata."""
    ctx = get_trace_context()

    with sentry_sdk.push_scope() as scope:
        scope.set_tag("stage", stage)
        scope.set_level(severity)

        for key, val in ctx.items():
            if val:
                scope.set_tag(key, val)

        if extra_metadata:
            for k, v in extra_metadata.items():
                scope.set_extra(k, v)

        sentry_sdk.capture_exception(error)


@contextmanager
def sentry_span(op: str, description: str) -> Generator[Any, None, None]:
    """Create a performance monitoring span in Sentry if a transaction is active."""
    try:
        with sentry_sdk.start_span(op=op, description=description) as span:
            ctx = get_trace_context()
            for key, val in ctx.items():
                if val:
                    span.set_data(key, val)
            yield span
    except Exception:
        yield None
