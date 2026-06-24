# 🛡️ NewsIQ LLM Gateway & Provider Resilience Design

This document describes the retry, backoff, and fallback mechanisms implemented in the LLM Gateway to ensure high availability and prevent silent failures.

---

## 1. LLM Gateway Architecture

The NewsIQ LLM Gateway acts as a resilient proxy between the application's processing tasks and external model providers (Google Gemini, Groq, Cohere, Cerebras, and OpenAI):

```
Application Stage (e.g. Summarization)
                  ↓
          [LLM Gateway Router]
                  ↓
         ┌────────┴────────┐
         ▼                 ▼
   Primary Provider   Fallback Pool
   (Gemini Flash)    (Groq / Cerebras)
         │                 │
         └────────┬────────┘
                  ▼
         [Key Cooldown Guard]
                  ▼
           LLM API Request
```

---

## 2. Cooldowns & Key Rate-Limit Handling

When a provider returns a rate limit or quota exception (HTTP 429), the gateway handles it dynamically:

1. **Mark Key as Cooling Down**: The specific API key is placed in a cooldown state in Redis with a timestamp (cooldown duration varies between 30 and 120 seconds depending on the provider).
2. **Key Rotation**: Subsequent requests rotate to the next active key in the provider pool.
3. **Pacing (Cooldown Sleep)**: If all keys for the primary provider are in cooldown, the gateway router calculates the remaining cooldown time of the key closest to expiration and pauses worker thread execution (up to 20 seconds) before retrying.
4. **Fallback Promotion**: If the cooldown wait exceeds 20 seconds, the router fails over to the next provider in the fallback chain.

---

## 3. Dynamic Fallback Chain

The fallback chain matches the model category requested:

* **Text Embeddings**:
  ```
  text-embedding-3-small (OpenAI) ──► cohere.embed-english-v3.0 ──► text-embedding-004 (Gemini)
  ```
* **Story Summarization & Extraction (High-Context)**:
  ```
  gemini-2.5-flash ──► llama-3.3-70b-versatile (Groq) ──► llama-3.1-405b (Cerebras)
  ```
* **Entity Linking / Deduplication (Fast-Reasoning)**:
  ```
  llama-3.1-8b-instant (Groq) ──► llama-3.1-8b (Cerebras) ──► gemini-2.5-flash
  ```

---

## 4. Cerebras & Cohere Pricing Mappings

To accurately compute LLM processing costs in `/admin/cost-analytics`, price schemas are registered in `cost_tracker.py` for all fallback endpoints:

| Model ID | Input Cost (per 1M tokens) | Output Cost (per 1M tokens) |
| :--- | :--- | :--- |
| `llama-3.1-8b` (Cerebras) | \$0.10 | \$0.10 |
| `llama-3.3-70b` (Cerebras) | \$0.60 | \$0.60 |
| `cohere.embed-english-v3.0` | \$0.10 | \$0.10 |
| `gemini-2.5-flash` | \$0.075 | \$0.30 |
| `text-embedding-3-small` | \$0.02 | \$0.02 |
