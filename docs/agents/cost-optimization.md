# Cost Optimization and Hybrid Architecture

NewsIQ's hybrid architecture minimizes API spending by combining deterministic algorithms with precision-focused agent execution.

## The 95% Deterministic / 5% Agentic Split

Routing every stage of a news processing pipeline through agents is prohibitively expensive. Instead, NewsIQ uses:

* **Deterministic Processing (95% of pipeline steps)**:
  * RSS Ingestion & Crawling.
  * Vector Embedding (using local or low-cost sentence transformers).
  * High-similarity clustering (Similarity > 0.90 automatically merges).
  * Low-similarity separation (Similarity < 0.70 automatically separates).
* **Agentic Processing (5% of pipeline steps)**:
  * **Ambiguity Handling**: Cluster verification runs ONLY when similarity is between 0.70 and 0.90.
  * **Knowledge Refinement**: Entity disambiguation runs only on unresolved names.
  * **Quality Validation**: Summaries are validated only after generation.

## Pricing Table

The `CostTracker` in [cost_tracker.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/llm_gateway/cost_tracker.py) computes real-time transaction costs per million tokens:

| Model ID | Input Cost (per 1M tokens) | Output Cost (per 1M tokens) |
| :--- | :--- | :--- |
| `gemini-2.5-flash-lite` | \$0.075 | \$0.30 |
| `gemini-2.5-flash` | \$0.15 | \$0.60 |
| `gpt-4o-mini` | \$0.15 | \$0.60 |
| `llama-3.1-8b-instant` | \$0.05 | \$0.08 |
| `llama-3.3-70b-specdec` | \$0.59 | \$0.79 |
| `mock` | \$0.00 | \$0.00 |

## Cost Analysis & Logging

Every successful LLM transaction records input/output tokens and cost in USD. These are saved to:
1. **Database telemetry**: The `llm_traces` PostgreSQL table.
2. **Prometheus Gauge**: `newsiq_llm_gateway_cost_usd` for live Grafana billing alerts.
