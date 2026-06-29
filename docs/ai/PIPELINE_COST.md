# NewsIQ Pipeline Stage-Level Cost Analysis

This document details the cost estimation metrics, token limits, and execution tracking of the AI synthesis pipeline.

---

## 1. Per-Stage Cost Profile

Using the `CostTracker` values, each pipeline stage has a designated cost profile per 100 articles processed:

| Stage | Avg. Input Tokens | Avg. Output Tokens | Estimated Cost / 100 Articles |
|---|---|---|---|
| **Event Extraction** | 2,500 | 300 | \$0.025 |
| **Entity Linking (Hybrid)** | 800 (Deterministic) | 200 (LLM Disambiguation) | \$0.006 (hybrid avg) |
| **Contradiction Detection** | 1,500 | 150 | \$0.016 |
| **Source Comparison** | 2,000 | 250 | \$0.022 |
| **Summary Generation** | 4,000 | 500 | \$0.090 |
| **Summary Reflection** | 4,500 | 200 | \$0.040 |

---

## 2. In-Memory Cache Optimization Impact

The introduction of the `PipelineCache` and `EmbeddingCache` significantly reduces total execution costs:
- **Exact Response Caching**: Returns a 30-40% reduction in LLM calls for recurring queries or minor updates.
- **Stage-Level Cache**: Prevents re-running contradiction and source comparison analysis when underlying article/story inputs have not changed.
- **Embedding Cache**: Eliminates 100% of re-embedding costs for static text.

---

## 3. Cost-Tracking Prometheus Gauges

The following metrics are exposed to track and alert on cost:
- `newsiq_llm_cost_dollars{provider, model, stage}`: Aggregated expenditure per model/stage.
- `newsiq_story_cost_usd{category}`: Aggregated cost per story cluster.
- `newsiq_story_stages_total{stage, status="skipped"}`: Counter representing skipped stages due to budget limits.

---

## 4. Grafana Dashboards

Cost limits are integrated into the Grafana billing dashboard with thresholds set at:
- **Warning**: Total hourly VM cost > \$0.50.
- **Critical**: Total daily LLM expenditure > \$15.00.
