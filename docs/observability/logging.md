# Structured Logging & Interception System

This document outlines the structured logging architecture in NewsIQ, detailing how logs are correlated, intercepted, stored, and streamed.

## Architecture

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

## Logging Processor

The `_store_and_publish_log` processor intercepts all logs that have both a `run_id` and a `stage` key:

1.  **Format Log Line**: Formats the log string to standard timestamp + level + message + extra format:
    ```
    2026-06-21T20:30:00Z [INFO] Deduplication started. {"articles_count": 42}
    ```
2.  **Redis Storage**: Appends the formatted log line to a Redis list at key `newsiq:logs:{run_id}:{stage}` with a 24-hour TTL.
3.  **Redis Broadcast**: Publishes the log line to a Redis Pub/Sub channel at key `newsiq:logs:{run_id}:{stage}:stream`.

## Endpoints

*   **GET `/admin/pipeline/runs/{run_id}/stages/{stage}/logs`**: Reads the compiled log list from the Redis database.
*   **GET `/admin/pipeline/runs/{run_id}/stages/{stage}/logs/stream`**: SSE endpoint that reads all historical logs from Redis and then subscribes to the Redis Pub/Sub channel to yield new log lines live.
