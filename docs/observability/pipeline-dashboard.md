# Pipeline Observability Dashboard

This document provides a guide to the NewsIQ Pipeline Observability Dashboard, located at `/dashboard/pipeline`. The dashboard acts as a real-time command center for monitoring and debugging our AI news intelligence pipeline.

## Overview

The dashboard visualizes the full execution flow (DAG) of the story intelligence pipeline:
```
[RSS Ingestion / GNews API] ──> [Deduplication & Embedding] ──> [NLP Analysis & Entity Linking] 
                                                                             │
[Search Indexing] <── [AI Summarization] <── [Contradiction Engine] <── [Story Clustering]
```

It behaves similarly to modern platform engineering platforms like Datadog, LangSmith, and Apache Airflow.

## Key Features

1. **Real-time Status Synchronization**: Employs Server-Sent Events (SSE) via `/api/v1/admin/pipeline/stream` to broadcast status updates live, without browser-side polling.
2. **Interactive Node DAG**: Every card in the pipeline DAG is clickable, serving as an entry point for localized telemetry.
3. **Execution Trace Inspection**: Allows SREs and developers to inspect any historical run by selecting it from the pipeline history table, changing the DAG to reflect that specific run's state.
4. **Unified Top Metrics Banner**: Displays connection status, active stage, total executions, total tokens, and overall LLM cost in real-time.

## Stage Node States

*   **Pending (Gray)**: Not yet executed or waiting for parent tasks to complete.
*   **Running (Blue)**: Currently processing with an active spinning loading indicator and card pulsing animation.
*   **Retrying (Yellow)**: Attempt failed and currently scheduling a retry backoff.
*   **Success (Green)**: Completed successfully within latency thresholds.
*   **Failed (Red)**: Failed during execution. Clicking reveals errors and stack trace.
*   **Skipped (Slate)**: Bypassed due to empty inputs (e.g. no new articles to embed).
