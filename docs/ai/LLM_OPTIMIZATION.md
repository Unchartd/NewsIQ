# NewsIQ LLM Cost Optimization & Budget Management

This document details the cost tracking, budget caps, and degradation policies implemented to ensure the NewsIQ AI pipeline operates cost-efficiently at scale.

---

## 1. Real-Time Cost Tracking

All LLM calls routed through the `RequestManager` are tracked for token usage and converted to real-time USD cost using the model pricing table defined in `CostTracker`.

- **Telemetry**: Cost metrics are pushed to Prometheus (`newsiq_llm_cost_dollars`) and aggregated per-story (`newsiq_story_cost_usd`).
- **Distributed Traces**: Cost is logged to the `llm_traces` database table via `track_llm_call`.

---

## 2. Cost Budget Manager

The `CostBudgetManager` enforces a cost limit per story. Budget caps vary depending on the story category's high-stakes nature:

| Story Type | Budget Cap | Categories / Conditions |
|---|---|---|
| **Default** | \$0.005 | Sports, Entertainment, Tech, Science |
| **High Stakes** | \$0.015 | World, Politics, Business, Health |
| **Breaking News** | \$0.020 | Story is flagged breaking or < 2 hours old |

---

## 3. Graceful Quality Degradation

When a story's accumulated cost exceeds its designated budget limit:
1. **Model Degradation**: Subsequent pipeline stages (e.g. event/entity extraction, contradiction checks) are downgraded to cheaper models (e.g. `gemini-2.5-flash-lite`).
2. **Optional Stage Skips**: The pipeline skips high-cost optional stages in order of priority:
   - **Step 1**: Skip Summary Reflection agent.
   - **Step 2**: Skip Summary Regeneration.
   - **Step 3**: Downgrade multi-agent cluster verification to deterministic-only.
3. **Core Preservation**: Critical stages (Event extraction, Entity linking, KG build, and base Summary generation) are **never** skipped.

---

## 4. Operational Controls

- **Budget Override**: Set `story.force_reflection = True` via admin panel to bypass budget restrictions and execute reflection on a critical story.
- **Circuit Breaker**: If Redis/caching fails, the cost tracking falls back to an in-memory dictionary. If all providers return quota errors (429), the pipeline enters an auto-paused cooldown state for 1 hour to prevent runaway billing attempts.
