# Agent Observability and Tracing

NewsIQ enforces strict telemetry and auditing on all AI/agentic actions. The system is designed to provide full explainability and token/cost accountability for every LLM invocation.

## Metrics Captured

Every agent run tracks and persists:
- **traceId**: The parent pipeline execution context trace.
- **runId**: The specific execution run identifier.
- **latency (duration)**: Time taken to complete the agent run.
- **tokens**: Detailed input/output/total token breakdown.
- **cost**: Calculated cost in USD based on model pricing.
- **provider**: The API provider (e.g. `google`, `openai`).
- **input / output**: The raw prompts and structured schemas emitted.
- **confidence**: Score returned by the agent.

## Telemetry Integrations

1. **Langfuse**: High-fidelity visualization of agent chains, spans, and prompt versions. Every LLM run maps to a `generation` or `span` in Langfuse.
2. **Prometheus / Grafana**: Real-time dashboards monitoring token counts, request rates, error rates, and cumulative costs.
3. **PostgreSQL Database**: Persistent auditing logs stored in the `llm_traces` and `stage_runs` tables.
4. **Sentry**: Auto-captures exceptions, rate-limit exhausts, or Pydantic validation failures.

## Logging Implementation

Observability is handled via the `run_agent_with_observability` wrapper which internally delegates telemetry tracking to the system's `track_llm_call` context manager.
