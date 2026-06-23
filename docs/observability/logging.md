# Structured Logging & Interception System

This document outlines the structured logging architecture in NewsIQ, detailing how logs are correlated, intercepted, stored, and streamed.

---

## 1. Structured Logging Flow

We use a unified logger based on `structlog` that overrides the standard library logging format. The pipeline injects runtime contextvars (`run_id`, `trace_id`, `span_id`, `stage`, `story_id`, and `article_id`) into every log record.

```
[Application Logs] ──> [Structlog Processors] ──> [JSON Console Output]
                                  │
                       [_store_and_publish_log]
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
            [Redis List (24h)]         [Redis Pub/Sub Channel]
             (Historical Logs)            (Live Log Streaming)
```

---

## 2. JSON Pino / OpenTelemetry Log Standard

To integrate cleanly with centralized collection agents (like Vector, Promtail, or OpenTelemetry Collector), all logs output to `stdout` in structured JSON format. This format is fully compatible with Pino and Datadog logging standards:

```json
{
  "level": "info",
  "time": "2026-06-22T20:30:00.124Z",
  "msg": "AI Summarization completed successfully.",
  "run_id": "76ba32c1-efef-4200-a29d-0932bcdef111",
  "trace_id": "90ab22cf-78ef-4100-88ad-0932bcdef778",
  "span_id": "aa123bcf-99ad-456b-bcde-0932bcdefaa4",
  "stage": "summary_generation",
  "story_id": "st_7781b2bc",
  "article_id": null,
  "provider": "gemini",
  "tokens": 4200,
  "latency_ms": 612.4,
  "cost_usd": 0.00012,
  "confidence": 0.985
}
```

---

## 3. Sentry & Error Interception

All uncaught exceptions inside the Processing or User backends are automatically captured by Sentry. The Sentry SDK is initialized in both backends, enriching each event payload with the tracing context:

```python
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from app.core.trace import run_id_ctx, trace_id_ctx, stage_ctx

def before_send(event, hint):
    """Enriches Sentry events with the active pipeline trace context."""
    run_id = run_id_ctx.get(None)
    trace_id = trace_id_ctx.get(None)
    stage = stage_ctx.get(None)
    
    if run_id:
        event["tags"] = event.get("tags", {})
        event["tags"]["run_id"] = str(run_id)
        event["tags"]["trace_id"] = str(trace_id)
        event["tags"]["stage"] = stage
        
    return event

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    integrations=[CeleryIntegration()],
    before_send=before_send,
    traces_sample_rate=1.0
)
```

---

## 4. Endpoints

*   **GET `/admin/pipeline/runs/{run_id}/stages/{stage}/logs`**: Reads the compiled log list from the Redis database.
*   **GET `/admin/pipeline/runs/{run_id}/stages/{stage}/logs/stream`**: SSE endpoint that reads all historical logs from Redis and then subscribes to the Redis Pub/Sub channel to yield new log lines live.
