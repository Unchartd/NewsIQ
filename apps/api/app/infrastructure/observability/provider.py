"""Observability infrastructure provider.

Wraps Langfuse and OpenTelemetry behind a single provider interface.
Business logic uses ObservabilityProvider for trace emission.
"""

from __future__ import annotations

import time
from typing import Any


class ObservabilityProvider:
    """Provides observability operations and health checks.

    Delegates to Langfuse (for LLM tracing) and OpenTelemetry (for
    distributed request tracing). All operations are fail-safe.
    """

    def trace(self, name: str, id: str, metadata: dict | None = None, **kwargs) -> Any:
        """Create or reference a Langfuse trace."""
        from app.core.langfuse_client import langfuse_client

        return langfuse_client.trace(name=name, id=id, metadata=metadata, **kwargs)

    def span(
        self,
        trace_id: str,
        name: str,
        id: str,
        parent_span_id: str | None = None,
        **kwargs,
    ) -> Any:
        """Create a Langfuse span under a trace."""
        from app.core.langfuse_client import langfuse_client

        return langfuse_client.span(
            trace_id=trace_id,
            name=name,
            id=id,
            parent_span_id=parent_span_id,
            **kwargs,
        )

    def generation(
        self,
        trace_id: str,
        span_id: str | None,
        model: str,
        name: str,
        input: Any,
        **kwargs,
    ) -> Any:
        """Record an LLM call generation in Langfuse."""
        from app.core.langfuse_client import langfuse_client

        return langfuse_client.generation(
            trace_id=trace_id,
            span_id=span_id,
            model=model,
            name=name,
            input=input,
            **kwargs,
        )

    async def health_check(self) -> dict:
        """Return a health status dict for the observability provider."""
        t0 = time.monotonic()
        from app.core.config import settings
        from app.core.langfuse_client import langfuse_client

        is_enabled = bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)
        client_ready = langfuse_client.client is not None

        latency_ms = (time.monotonic() - t0) * 1000
        return {
            "status": "ok" if (not is_enabled or client_ready) else "degraded",
            "langfuse_enabled": is_enabled,
            "langfuse_connected": client_ready,
            "langfuse_host": settings.LANGFUSE_HOST,
            "latency_ms": round(latency_ms, 2),
        }

    async def flush(self) -> None:
        """Flush all pending Langfuse events. Call during application shutdown."""
        from app.core.langfuse_client import langfuse_client

        if langfuse_client.client:
            try:
                langfuse_client.client.flush()
            except Exception:
                pass


observability_provider = ObservabilityProvider()
