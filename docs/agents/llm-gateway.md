# Unified LLM Gateway

The **LLM Gateway** is a single entry point for all LLM calls in NewsIQ. Its design guarantees that no module directly invokes external APIs, allowing central control over rate limiting, retries, fallbacks, cost monitoring, and logging.

## Request Lifecycle

When a client initiates a request via `llm_gateway.execute_request`, the following lifecycle executes:

```text
[Client Call]
    ↓
[Get Fallback Chain] ── (Gemini -> Groq -> OpenAI -> Mock)
    ↓
[For each model in chain]
    ↓
  [Select Key & Client] ── (Selects healthy key, checks cooldowns)
    ↓
  [Rate Limit Check] ──── (Verifies RPM/RPD sliding windows)
    ↓
  [Record Request] ────── (Updates sliding window timestamps)
    ↓
  [DB Span Tracing] ───── (Starts track_llm_call context manager)
    ↓
  [Call Client API]
   ├── Success ─────────> [Report Success] ──> [Expose Metrics] ──> [Return Response]
   └── Error (429/500) ──> [Report Failure] ──> [Cooldown Key] ──> [Try Next Fallback]
```

## Key Modules

* **[base_provider.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/llm_gateway/base_provider.py)**: Establishes `GatewayRequest`, `GatewayResponse`, and the abstract `BaseLLMProvider`.
* **[provider_pool.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/llm_gateway/provider_pool.py)**: Concrete client adapters for Gemini, OpenAI, Groq, and Mock.
* **[request_manager.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/llm_gateway/request_manager.py)**: The orchestrator managing fallback chains and retry/failover routing.

## Structured Outputs Integration

Structured output schemas (Pydantic models) passed in `response_format` are mapped:
* **Gemini**: Handled natively using `GenerateContentConfig(response_schema=schema, response_mime_type="application/json")`.
* **OpenAI & Groq**: Handled using client parsing utilities: `client.beta.chat.completions.parse(..., response_format=schema)`.
* **Mock**: Yields a deterministic JSON structure conforming to the target schema for local development or emergency fallbacks.
