# Stage Runs & Trace Telemetry Schema

This document details the database models used to track execution context, durations, LLM telemetry, prompts, and tokens.

## DB Schema Layout

Observability database records are split across three primary models:

### 1. `pipeline_runs` (`PipelineRunModel`)
Tracks top-level pipeline executions.
*   `id`: Primary Key (UUID v7/v4).
*   `trace_id`: Unique tracing ID. Propagates down to Celery workers.
*   `trigger`: Trigger source (`celery_beat`, `manual`, `replay`, `api`).
*   `status`: Current overall status (`pending`, `running`, `success`, `failed`).
*   `started_at` & `completed_at`: UTC timestamps.
*   `total_latency_ms`: Total execution time.

### 2. `stage_runs` (`StageRunModel`)
Tracks individual stage spans inside a pipeline run.
*   `id`: Stage span ID.
*   `run_id`: Foreign Key referencing `pipeline_runs.id`.
*   `trace_id`: Tracing correlation ID.
*   `stage`: Lowercase canonical stage identifier (e.g. `entity_extraction`, `contradiction_detection`).
*   `status`: Status of the stage (`pending`, `running`, `success`, `failed`, `skipped`).
*   `latency_ms`: Duration of this stage.
*   `retry_count`: Count of failed attempts before completing or failing.
*   `error` & `error_type`: Captures exception type and message.
*   `metadata`: JSONB payload containing `inputs` and `outputs`.

### 3. `llm_traces` (`LLMTraceModel`)
Tracks individual LLM API requests made to Gemini and OpenAI.
*   `id`: Call tracing ID.
*   `run_id` & `trace_id`: Linking references back to the execution pipeline.
*   `provider`: API provider (`gemini`, `openai`).
*   `model`: Model name (e.g. `gemini-2.5-flash-lite`, `gpt-4o-mini`).
*   `system_prompt` & `user_prompt`: The prompts sent to the LLM.
*   `response_text`: The raw response content.
*   `input_tokens`, `output_tokens`, `total_tokens`: Token metrics.
*   `cost_usd`: Real-time computed API cost.
*   `latency_ms`: Response duration.
