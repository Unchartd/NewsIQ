# NewsIQ Observability Platform Architecture

This document details the architectural design and operations of the NewsIQ AI Observability, Tracing, and Replay Platform.

---

## 1. System Overlay Diagram

The following diagram illustrates how telemetry is woven into the standard news intelligence ingestion and synthesis pipeline:

```mermaid
graph TD
    %% Pipeline Steps
    RSS[RSS / GNews Ingestion] --> Crawl[Full-Text Crawler]
    Crawl --> Embed[Gemini Embeddings]
    Embed --> EventExt[Structured Event Extraction]
    EventExt --> EntityExt[NER / Wikidata Linking]
    EntityExt --> KG[Knowledge Graph Builder]
    KG --> Cluster[HDBSCAN Clustering]
    Cluster --> Contradict[Contradiction Engine]
    Contradict --> Synthesis[AI Synthesis Summarizer]
    Synthesis --> Search[Meilisearch / Cache Push]

    %% Observability Context
    subgraph Tracing Context (trace.py)
        PR[PipelineRun: contextvars run_id/trace_id]
        SS[StageSpan: contextvars span_id/stage]
    end
    PR -.-> SS
    SS -.-> RSS & Crawl & Embed & EventExt & EntityExt & KG & Cluster & Contradict & Synthesis & Search

    %% Telemetry Output
    SS --> |JSON Log| Structlog[Structlog Engine]
    SS --> |Counters/Histograms| Prom[Prometheus Scraper]
    SS --> |Trace/Generation Spans| Langfuse[Langfuse Client]
    SS --> |DB Records| Postgre[Postgres Observability Tables]
    SS --> |Pub/Sub Events| Redis[Redis Broker]

    %% Real-time UI & Admin Consoles
    Redis --> |EventStream| SSE[FastAPI SSE Router]
    SSE --> |useSSE hook| UI[Next.js Admin Console]
```

---

## 2. Split-Backend Architecture

To protect user responsiveness and enforce reliability boundaries, the NewsIQ system is split into two distinct execution backends:

```
┌────────────────────────────────────────────────────────┐
│               NEWSIQ PROCESSING BACKEND                │
│ (Celery workers, LLM Gateways, Vector DBs, Crawlers)   │
├────────────────────────────────────────────────────────┤
│ Ingestion ──> Extraction ──> Embeddings ──> Clustering  │
│ ──> Timeline ──> Synthesis ──> Publishing (to Cache)   │
└──────────────────────────┬─────────────────────────────┘
                           │ (Publishes to DB / Cache)
                           ▼
┌────────────────────────────────────────────────────────┐
│                 NEWSIQ USER BACKEND                    │
│      (FastAPI, Auth service, Feeds delivery)           │
├────────────────────────────────────────────────────────┤
│ Auth ──> Recommendations ──> Search ──> Delivery API   │
└────────────────────────────────────────────────────────┘
```

### 2.1 Processing Backend
*   **Responsibilities:** RSS/GNews fetching, raw web scraping, embedding calculation, HDBSCAN clustering, Wikidata linking, contradiction audits, AI summarization, reflection checks, and cache warming.
*   **Operational Boundary:** Operates asynchronously in background worker processes. It is completely isolated from user traffic. Even if LLM latency spikes or API rate limits are hit, user API services are unaffected.

### 2.2 User Backend
*   **Responsibilities:** User login/session authentication, bookmark tracking, personal feeds generation, Meilisearch queries, and user notification triggers.
*   **Operational Boundary:** Enforces strict execution limits (latencies under 100ms). It queries pre-computed summaries and story clusters from the database or Meilisearch caches and **never** awaits or initiates long-running AI generation jobs directly.

---

## 3. Telemetry Primitives

### 3.1 Context Propagation (`trace.py`)
Because Celery workers execute asynchronously in a multi-process pool, thread-local storage is insufficient. The platform utilizes Python's native `contextvars` to manage stack-safe, async-safe tracing variables:

*   `run_id_ctx`: UUID of the parent pipeline run execution.
*   `trace_id_ctx`: Propagation trace correlation ID (shared by DB, Sentry, and Langfuse).
*   `span_id_ctx`: UUID of the currently executing stage span.
*   `story_id_ctx` / `article_id_ctx`: Context binders for entity matching.

These variables are automatically bound to:
1.  **Sentry Transaction Breadcrumbs** and tags.
2.  **Structlog JSON output payloads**.
3.  **Langfuse generations and traces**.

---

## 4. Database Schema

All database models are managed via SQLAlchemy under `app/models/observability_models.py`:

> **Which of these actually carry data.** Row counts measured in production on
> 2026-08-16 during the observability audit. Several tables are modelled and
> migrated but have never been written, so treat this section as the schema, not
> as a description of what is collected. See `docs/Observability_Audit.md`.

### 4.1 Core Telemetry Tables
*   `pipeline_runs` — **live (6,318 rows)**. Records the execution trigger (`celery_beat`, `manual`, `chained`), type (`batch`, `incremental`), starting/ending timestamps, overall latency, and termination status.
*   `stage_runs` — **live (31,796 rows)**. Stores granular timing, retries, and error traceback payloads for each pipeline stage. Linked to `pipeline_runs`.
*   `llm_traces` — **live (17,333 rows)**. Logs every LLM completion: model, provider, prompts, response, tokens, cost, latency. Two caveats: prompts are stored only for errors, `DEBUG`, or sampled calls, and `cost_usd` read 0.00 on every row until the pricing consolidation (#123) — see below.
*   `queue_metrics` — **live (9,332 rows)**. Snapshots Redis queue lengths and Celery worker health.
*   `error_logs` — **empty (0 rows). No writer exists.** Stage logs live in Redis under a 24-hour TTL instead; a bounded tail is snapshotted into `stage_runs.metadata.logs_tail` when a stage fails (#126). The table is retained deliberately as the natural home for a durable log store.
*   ~~`function_runs`~~ — **removed (#128)**. Never written, no reader, no endpoint; the table is dropped by migration `f1b6d3e90a24`.

Also present and live, though not originally listed here:

*   `pipeline_traces` — **live (9,856 rows)**. Written by the synthesis orchestrator, and the only place the seven synthesis stages were recorded until #124 mirrored them into `stage_runs`.
*   `ai_execution_records` — **live (3,794 rows)**, richer than `llm_traces` (decision, confidence, cache hit, schema repair, prompt version) and **currently read by nothing**.
*   `pipeline_failures` — **live (331 rows)**. Backs the Failure Center.
*   `story_evolutions` — **live (716 rows)**.
*   `token_usage`, `cost_records`, `retry_history` — **empty (0 rows), no writer.** Retained as the intended destinations for gaps the audit identified (token capture, cost records).

### 4.2 Human Review & Replay Tables
*   `human_reviews` — **empty (0 rows), but not dead.** `admin_service` writes a row from `POST /admin/review/{story_id}/action`, which the admin UI calls. It is empty because the action has not been used, not because nothing reaches it. Stores manual interventions (approvals, rejections, cluster splits/merges, entity overrides) with Before/After JSON diffs and notes.
*   `prompt_versions` — **stale (18 rows, last written 2026-07-14).** Retains hash-deduplicated system/user templates for LLM tasks. `/admin/prompt-analytics` reads it and has no frontend consumer, so it currently surfaces month-old data.

---

## 5. Real-time Streaming (SSE)

Real-time transitions are streamed using HTML5 Server-Sent Events (SSE):

1.  Inside `StageSpan.__aenter__` and `StageSpan.__aexit__`, a JSON status payload is published to Redis on the channel `newsiq-pipeline-events`.
2.  The FastAPI `/api/v1/admin/pipeline/stream` endpoint subscribes to this channel using `redis.asyncio` and streams events continuously as `text/event-stream`.
3.  The frontend client consumes the stream using the React `useSSE` hook, triggering visual DAG state transitions in the admin console.

---

## 6. Replay Engine Architecture

Replays are executed out-of-band in separate background Celery processes to prevent freezing Web UI operations:

*   **Full Replay**: Reloads the target story's original articles from the DB, and runs `clustering_service.generate_story_content(story, articles, db)` inside a `PipelineRun(is_replay=True)` block, overwriting syntheses and index entries.
*   **Stage Replay**: Isolates specific components (e.g. NER/Entity linking, timeline generation, summarization) and runs only their associated service logic while preserving other story data.
