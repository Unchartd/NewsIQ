"""Langfuse client wrapper for LLM observability.

Provides a robust, no-op safe wrapper around the Langfuse SDK that integrates
with the NewsIQ pipeline trace context.
"""

from __future__ import annotations

import logging
from typing import Any

from langfuse import Langfuse

from app.core.config import settings

logger = logging.getLogger(__name__)


class DummySpan:
    """A no-op placeholder returned when Langfuse is disabled or errors occur."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def span(self, *args, **kwargs) -> DummySpan:
        return self

    def generation(self, *args, **kwargs) -> DummySpan:
        return self

    def score(self, *args, **kwargs) -> DummySpan:
        return self

    def event(self, *args, **kwargs) -> DummySpan:
        return self

    def end(self, *args, **kwargs) -> DummySpan:
        return self

    def update(self, *args, **kwargs) -> DummySpan:
        return self


class LangfuseClientWrapper:
    """Wrapper around Langfuse SDK that fails gracefully when keys are missing."""

    def __init__(self) -> None:
        self.client: Langfuse | None = None
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                self.client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("Langfuse client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse client: {e}")
        else:
            logger.info("Langfuse keys not set. LLM tracing to Langfuse is disabled.")

    def trace(
        self,
        name: str,
        id: str,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> Any:
        """Create or reference a trace in Langfuse."""
        if not self.client:
            return DummySpan()
        try:
            return self.client.trace(name=name, id=id, metadata=metadata, **kwargs)
        except Exception as e:
            logger.warning(f"Langfuse trace creation failed: {e}")
            return DummySpan()

    def span(
        self,
        trace_id: str,
        name: str,
        id: str,
        parent_span_id: str | None = None,
        **kwargs,
    ) -> Any:
        """Create a span under a specific trace and optional parent span."""
        if not self.client:
            return DummySpan()
        try:
            trace = self.client.trace(id=trace_id)
            if parent_span_id:
                parent = trace.span(id=parent_span_id)
                return parent.span(id=id, name=name, **kwargs)
            return trace.span(id=id, name=name, **kwargs)
        except Exception as e:
            logger.warning(f"Langfuse span creation failed: {e}")
            return DummySpan()

    def generation(
        self,
        trace_id: str,
        span_id: str | None,
        model: str,
        name: str,
        input: Any,
        model_parameters: dict[str, Any] | None = None,
        **kwargs,
    ) -> Any:
        """Record an LLM call (generation) under a trace and optional parent span."""
        if not self.client:
            return DummySpan()
        try:
            trace = self.client.trace(id=trace_id)
            parent = trace.span(id=span_id) if span_id else trace
            return parent.generation(
                name=name,
                model=model,
                input=input,
                model_parameters=model_parameters,
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"Langfuse generation creation failed: {e}")
            return DummySpan()


# Global Langfuse client wrapper instance
langfuse_client = LangfuseClientWrapper()
