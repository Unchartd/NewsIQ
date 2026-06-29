# NewsIQ Centralized Model Routing

This document details the centralized LLM model selection logic configured in the NewsIQ platform via `ModelRouter`.

---

## 1. Centralized Routing Philosophy

No backend service or LLM gateway call should hardcode an LLM model name directly. Instead, services supply their current `stage` name and input `complexity`. The `ModelRouter` determines the smallest, most cost-effective model that meets the quality threshold for that specific task.

---

## 2. Dynamic Routing Table

The router maps stages to models based on the current complexity and cost-budget states:

| Pipeline Stage | Standard Complexity | Complex Input | Budget Exceeded |
|---|---|---|---|
| **Event Extraction** | `gemini-2.5-flash-lite` | `gemini-2.5-flash` | `gemini-2.5-flash-lite` |
| **Entity Linking** | `gemini-2.5-flash-lite` | `gemini-2.5-flash` | `gemini-2.5-flash-lite` |
| **Contradiction Detection** | `gemini-2.5-flash-lite` | `gemini-2.5-flash` | `gemini-2.5-flash-lite` |
| **Source Comparison** | `gemini-2.5-flash-lite` | `gemini-2.5-flash` | `gemini-2.5-flash-lite` |
| **Summary Generation** | `gemini-2.5-flash` | `gemini-2.5-pro` | `gemini-2.5-flash` |
| **Summary Reflection** | `gemini-2.5-flash-lite` | `gemini-2.5-flash` | *Skip reflection* |
| **Cluster Verification** | `gemini-2.5-flash-lite` | `gemini-2.5-flash` | `gemini-2.5-flash-lite` |

---

## 3. Complexity Scoring

Complexity is determined dynamically by assessing the input payload sizes:
- **Standard**: Context length is within standard bounds (e.g. < 10,000 characters).
- **Complex**: Context exceeds threshold (e.g. >= 10,000 characters), triggering routing to larger context window models (e.g. `gemini-2.5-flash` or `gemini-2.5-pro`).

---

## 4. Configuration

The routing table is configurable in the application settings via `MODEL_ROUTING_TABLE`, allowing instant updates across all pipeline stages without requiring code redeployments.
