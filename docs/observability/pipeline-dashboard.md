# Pipeline Observability Dashboard

This document provides a guide to the NewsIQ Pipeline Observability Dashboard, located at `/admin/pipeline`. The dashboard acts as a real-time command center for monitoring and debugging our AI news intelligence pipeline.

---

## 1. Unified Top Metrics Bar

The header of `/admin/pipeline` displays live key performance indicators (KPIs) aggregated over the last 24 hours:

*   **Status:** Connected (SSE Stream Active).
*   **Active Stage:** Displays the stage currently executing (e.g. `HDBSCAN Clustering`).
*   **Total Executions:** Count of pipeline runs today.
*   **Total Tokens consumed:** Live counter of tokens processed today.
*   **Pipeline Cost:** Real-time computed dollar cost of AI calls today.

---

## 2. Interactive Pipeline DAG

The central area of the dashboard displays the active Directed Acyclic Graph (DAG) representing the 11 processing stages:

```
[RSS Ingestion] ──> [Extraction] ──> [Embedding] ──> [Event Extraction] 
                                                              │
[Timeline] <── [Clustering] <── [Entity Linking] <── [Entity Extraction]
    │
[Summary] ──> [Reflection] ──> [Publishing]
```

### Stage Card Visual States
*   **Pending (Gray):** Not yet executed or waiting for parent tasks to complete.
*   **Running (Pulsing Blue):** Currently processing with an active spinning loader.
*   **Retrying (Yellow):** Attempt failed and currently scheduling a backoff timer.
*   **Success (Green):** Completed successfully within latency thresholds.
*   **Failed (Red):** Executing step raised an exception. Clicking opens the Stage Detail panel containing the traceback logs.
*   **Skipped (Slate):** Bypassed due to empty inputs (e.g., no new articles found).

---

## 3. Real-Time Status Stream (SSE)

We use Server-Sent Events (SSE) instead of HTTP polling to maintain low server load. The Next.js frontend establishes a single subscription to `/api/v1/admin/pipeline/stream`:

```javascript
// useSSE hook inside apps/web/src/app/admin/pipeline/page.tsx
useEffect(() => {
  const eventSource = new EventSource('/api/v1/admin/pipeline/stream');
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateDAGNodeState(data.stage, data.status, data.run_id);
  };
  
  return () => eventSource.close();
}, []);
```

---

## 4. Stage Detail Panel

Clicking on any stage card in the DAG opens a side drawer displaying detailed telemetry for that specific stage execution:

*   **Overview:** Start time, duration, retry count, status.
*   **Inputs / Outputs:** Collapsible JSON trees of raw feed text or extracted entity arrays.
*   **Metrics:** Latency, input/output token counts, estimated cost.
*   **Logs:** Real-time log stream filtered specifically to `newsiq:logs:{run_id}:{stage}`.
*   **Error Panel:** Displays error categorization, exception details, and raw tracebacks.
*   **Model Config:** Version of system prompts, LLM provider, and model configurations used.
