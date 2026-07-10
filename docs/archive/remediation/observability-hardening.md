# 📊 NewsIQ Observability & Pipeline Hardening Design

This document details the implementation of the NewsIQ Failure Center and the distributed tracing framework used to capture and debug background processing errors.

---

## 1. Structured Database Logging: The `pipeline_failures` Table

To stop silent failures, we treat processing exceptions as first-class, queryable data entities. We store raw inputs, trace contexts, and Python tracebacks inside PostgreSQL using a dedicated `pipeline_failures` table.

```
       +---------------------------------------------+
       |             pipeline_failures               |
       +---------------------------------------------+
       | id               : UUID (PK)                |
       | trace_id         : UUID (Index)             |
       | stage            : VARCHAR(100)             |
       | provider/model   : VARCHAR                  |
       | status           : VARCHAR(30)              |
       | input_payload    : JSONB                    |
       | output_payload   : JSONB                    |
       | raw_response     : TEXT                     |
       | exception        : TEXT                     |
       | stack_trace      : TEXT                     |
       | error_category   : VARCHAR(50) (Index)      |
       | error_code       : VARCHAR(100)             |
       | timestamp        : TIMESTAMP (Index)        |
       | resolved         : BOOLEAN (Index)          |
       | resolution_notes : TEXT                     |
       +---------------------------------------------+
```

---

## 2. Distributed Tracing using `StageSpan`

The `StageSpan` context manager (`app/core/trace.py`) wraps pipeline stages and manages context variables (`trace_id`, `run_id`, `stage_name`).

### Key Functions of `StageSpan`:
1. **Context Initialization**: On entry (`__aenter__`), it generates or propagates a `trace_id` and registers the current pipeline stage.
2. **Payload Preservation**: It provides methods to save raw stage inputs (e.g., article text body or Qdrant search results).
3. **Automatic Exit Interceptor**: On exit (`__aexit__`), if an exception is raised:
   * It intercepts the exception.
   * It extracts the stack trace and formats the error.
   * It classifies the error (e.g., mapping HTTP 429 to `llm_error` with sub-code `RATE_LIMIT_EXCEEDED`).
   * It writes a new failure record directly to `pipeline_failures` before bubbling the exception up.

---

## 3. The Failure Center SRE Dashboard

The Next.js admin console fetches these failure logs to provide an SRE-focused workspace:
* **Search & Filters**: Search failures by trace ID, exception text, or filter by stage (e.g., `clustering`, `summary_generation`) and error category.
* **Payload Viewer**: Inspect raw inputs and outputs in JSON format.
* **Resolution Workflow**: Allows developers to mark a failure as resolved and save notes.
* **Inline Replays**: Provides a replay button to re-run individual stages with model/provider overrides.
