# NewsIQ Observability Platform — Roadmap

> **Generated**: 2026-06-20
> **Status**: In Progress

---

## Vision

Build a Bloomberg Terminal / LangSmith / Datadog-grade observability platform for the NewsIQ news intelligence pipeline. Every pipeline stage must be **traceable, replayable, measurable, and debuggable**.

---

## Execution Tiers

### Tier 1: Foundation ✅ IN PROGRESS
**Phases 1-4 | ~3000 lines | Backend-only**

| Phase | Milestone | Acceptance Criteria |
|-------|-----------|-------------------|
| 1 | Pipeline Audit | `docs/observability/current-pipeline.md` exists with full gap analysis |
| 2 | Trace Model | Every Celery task emits `run_id` + `trace_id`. `PipelineRun` + `StageRun` tables populated |
| 3 | DB Models | All observability models migrated: `LLMTrace`, `TokenUsage`, `CostRecord`, `RetryHistory`, `PromptVersion`, `ErrorLog`, `QueueMetrics` |
| 4 | Structured Logging | All services use structlog with bound `trace_id`, `stage`, `latency_ms`. JSON output includes full context |

### Tier 2: External Integrations
**Phases 5-8 | ~2500 lines | Adds Docker services**

| Phase | Milestone | Acceptance Criteria |
|-------|-----------|-------------------|
| 5 | Langfuse | Every LLM call captured with prompt, response, tokens, cost. Viewable at `localhost:3100` |
| 6 | Flower | Queue health visible at `localhost:5555`. Dead-letter queue configured |
| 7 | Sentry | All errors enriched with `trace_id`, `story_id`. Frontend errors captured |
| 8 | Prometheus | `/metrics` endpoint returns all pipeline metrics. Prometheus scraping confirmed |

### Tier 3: Admin UI
**Phases 9-18 | ~8000 lines | Frontend panels**

| Phase | Milestone | Acceptance Criteria |
|-------|-----------|-------------------|
| 9 | Grafana | 8 auto-provisioned dashboards at `localhost:3001` |
| 10 | Story Inspector | `/admin/stories/[id]` shows full story trace with all sub-data |
| 11 | Pipeline DAG | `/admin/pipeline` shows real-time stage status with color coding |
| 12 | SSE Streaming | Pipeline DAG updates in real-time without polling |
| 13 | Prompt Viewer | `/admin/prompts` shows versioned prompts with diffs |
| 14 | Cost Analytics | `/admin/costs` shows per-provider, per-story cost breakdowns |
| 15 | Entity Debugger | `/admin/entities` shows raw → canonical mapping with corrections |
| 16 | Cluster Debugger | `/admin/clusters` shows similarity matrices and merge decisions |
| 17 | Timeline Debugger | `/admin/timeline` shows chronological event ordering |
| 18 | Human Review | `/admin/review` supports approve/reject/split/merge with feedback storage |

### Tier 4: Replay System
**Phase 19 | ~1500 lines**

| Phase | Milestone | Acceptance Criteria |
|-------|-----------|-------------------|
| 19 | Replay | Can replay any story or individual stage. Side-by-side diff of original vs replayed output |

### Tier 5: Documentation
**Phase 20 | ~2000 lines**

| Phase | Milestone | Acceptance Criteria |
|-------|-----------|-------------------|
| 20 | Docs | Complete `/docs/observability/` with 14 markdown guides |

---

## Future Enhancements (Post-MVP)

- **Anomaly Detection**: Auto-detect quality degradation in summaries
- **A/B Testing**: Compare prompt versions with quality metrics
- **Model Evaluation**: Automated evaluation of summary quality using LLM-as-judge
- **Alerting**: PagerDuty/Slack integration for critical pipeline failures
- **Data Lineage**: Full provenance graph from raw RSS entry to final story
- **Multi-tenant Observability**: Per-user pipeline analytics
- **Custom Metric Queries**: Ad-hoc PromQL queries from admin UI
