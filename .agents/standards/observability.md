# observability.md — Observability Standards for NewsIQ

This standard defines distributed tracing, application metrics, and health reporting structures.

## 1. Tracing (OpenTelemetry)
- **Spans**: Wrap significant transactions (e.g. RSS item parsing, clustering routines, LLM reflection runs) inside distinct OpenTelemetry trace spans.
- **Attributes**: Annotate spans with useful domain variables (e.g., `newsiq.story.id`, `newsiq.llm.model`, `newsiq.pipeline.stage`), but never log raw personal user data.

## 2. Metric Collections
- **Naming Conventions**: Use standard snake_case with units (e.g., `newsiq_api_request_duration_seconds`, `newsiq_pipeline_failed_runs_total`).
- **Standard Counters**:
  - `Request counters`: Track path, method, and HTTP status codes.
  - `Queue sizes`: Redis background job depths.
  - `LLM tracking`: Token consumption, latency, and cost estimates.
