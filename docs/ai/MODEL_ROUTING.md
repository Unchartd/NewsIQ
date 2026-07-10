# NewsIQ Centralized Model Routing

This document details the centralized LLM model selection and fallback logic configured in the NewsIQ platform via `CapabilityRouter` and `AIGateway`.

---

## 1. Centralized Routing Philosophy

No backend service or LLM gateway call should hardcode an LLM model name directly. Instead, services supply their current `capability` name and request parameters. The `CapabilityRouter` resolves a prioritized chain of healthy, available providers and models, executing fallovers automatically on errors, timeouts, or circuit trips.

---

## 2. Capability-Based Routing Table

The router maps specific processing capabilities to a multi-stage execution chain (`primary` ➡️ `fallback` ➡️ `lastFallback`):

### A. Flash Capabilities (Latency & Cost Optimized)

Used for event/entity extraction, classification, and metadata generation.

| Capability | Primary Route | Fallback Route | Last Fallback Route | Temperature | Timeout |
|---|---|---|---|---|---|
| `event_extraction` | `nvidia` (`deepseek-v4-flash`) | `gemini` (`gemini-2.5-flash`) | `openrouter` (`deepseek-chat`) | 0.1 | 30.0s |
| `entity_extraction` | `nvidia` (`deepseek-v4-flash`) | `gemini` (`gemini-2.5-flash`) | `openrouter` (`deepseek-chat`) | 0.1 | 30.0s |
| `entity_linking` | `nvidia` (`deepseek-v4-flash`) | `gemini` (`gemini-2.5-flash`) | `openrouter` (`deepseek-chat`) | 0.1 | 15.0s |
| `topic_classification` | `nvidia` (`deepseek-v4-flash`) | `gemini` (`gemini-2.5-flash`) | `openrouter` (`deepseek-chat`) | 0.1 | 15.0s |
| `keyword_generation` | `nvidia` (`deepseek-v4-flash`) | `gemini` (`gemini-2.5-flash`) | `openrouter` (`deepseek-chat`) | 0.3 | 15.0s |
| `cluster_verification`| `nvidia` (`deepseek-v4-flash`) | `gemini` (`gemini-2.5-flash`) | `openrouter` (`deepseek-chat`) | 0.1 | 30.0s |
| `contradiction_detection`| `nvidia` (`deepseek-v4-flash`)| `gemini` (`gemini-2.5-flash`) | `openrouter` (`deepseek-chat`) | 0.1 | 30.0s |
| `summary_reflection` | `nvidia` (`deepseek-v4-flash`) | `gemini` (`gemini-2.5-flash`) | `openrouter` (`deepseek-chat`) | 0.1 | 30.0s |

### B. Pro Capabilities (Quality & Context Optimized)

Used for story timeline building, contradiction analysis, source comparison, and final synthesis.

| Capability | Primary Route | Fallback Route | Last Fallback Route | Temperature | Timeout |
|---|---|---|---|---|---|
| `timeline` | `nvidia` (`deepseek-v4-pro`) | `gemini` (`gemini-2.5-pro`) | `openrouter` (`qwen-2.5-72b`) | 0.1 | 30.0s |
| `story_synthesis` | `nvidia` (`deepseek-v4-pro`) | `gemini` (`gemini-2.5-pro`) | `openrouter` (`qwen-2.5-72b`) | 0.1 | 45.0s |
| `difference_engine` | `nvidia` (`deepseek-v4-pro`) | `gemini` (`gemini-2.5-pro`) | `openrouter` (`qwen-2.5-72b`) | 0.1 | 30.0s |
| `contradiction_analysis`| `nvidia` (`deepseek-v4-pro`)| `gemini` (`gemini-2.5-pro`) | `openrouter` (`qwen-2.5-72b`) | 0.1 | 30.0s |
| `source_comparison` | `nvidia` (`deepseek-v4-pro`) | `gemini` (`gemini-2.5-pro`) | `openrouter` (`qwen-2.5-72b`) | 0.1 | 30.0s |
| `summary_generation` | `nvidia` (`deepseek-v4-pro`) | `gemini` (`gemini-2.5-pro`) | `openrouter` (`qwen-2.5-72b`) | 0.1 | 60.0s |

### C. Embedding Capabilities

| Capability | Primary Route | Fallback Route | Last Fallback Route | Temperature | Timeout |
|---|---|---|---|---|---|
| `embedding` | `gemini` (`text-embedding-004`) | `nvidia` (`nvidia/llama-3.2-nv-embedqa-4b-v1`) | `openrouter` (`nomic/nomic-embed-text-v1.5`) | 0.0 | 15.0s |

---

## 3. Circuit Breaker & Health Tracking

To prevent cascading failures and API request latency overhead, the `CapabilityRouter` implements a circuit-breaker pattern per provider (`gemini`, `nvidia`, `openrouter`):

- **Health Monitoring**: `ProviderHealthTracker` instances monitor all successes and failures on LLM API calls.
- **Circuit Tripping (OPEN)**: If a provider experiences **3 consecutive failures** (e.g. rate limits, timeouts, authentication errors), the circuit trips to `OPEN`. That provider is marked unhealthy and disabled for **5 minutes**.
- **Self-Healing (HALF-OPEN)**: After the 5-minute timeout expires, the next call is allowed through to test recovery. A single success closes the circuit; a failure keeps it tripped.
- **Background Heartbeat Check**: When a provider is unhealthy, a background fire-and-forget task runs every **2 minutes** to test health using a minimal request and revive the provider automatically if successful.

---

## 4. Key Rotation & Cooldowns

To maximize throughput and avoid rate-limiting limits, the router manages an API key pool per provider:

- **Key Rotation**: When a key is requested, the router rotates keys in a round-robin/priority fashion.
- **Cooldowns**: If a key hits a rate limit (429), it is placed on a cooldown period (e.g. 10s for Gemini). The router will bypass cooling keys and select the next available healthy key.
- **Safe Fallback**: If all keys for a provider are in cooldown, the router selects the one whose cooldown expires soonest.

---

## 5. Gateway Migration & Deprecation Strategy

To support unified capability-based routing and a simpler developer experience, Gateway B (`llm_gateway`) is being deprecated in favor of the new Unified Gateway A (`AIGateway`).

### A. Safe Rollback Feature Flag
The migration is governed by a global feature flag:
- **`USE_NEW_GATEWAY`** (boolean, defaults to `True`): When enabled, all calls to `llm_gateway` and `GatewayModel` are routed to the new `AIGateway`. If disabled, requests flow through the legacy Gateway B fallback paths.

### B. Configuration-Driven Model Fallbacks
Provider routing is configured via the `MODEL_FALLBACKS` dictionary in `app/ai/config.py`. Only **Gemini, NVIDIA NIM, and OpenRouter** are supported. Groq and Cerebras are excluded.

### C. Deprecated Endpoint Forwarding
To ensure backward compatibility during the transition, `RequestManager` (the old gateway) async and sync entry points (`execute_request` and `execute_request_sync`) act as thin proxies that log a warning and delegate directly to the unified `AIGateway` if the feature flag is enabled.

### D. Budget & Token Guards
Pro capability models are protected by the `MAX_PRO_MODEL_TOKENS` budget guard which counts input prompt tokens and truncates input content if it exceeds the limit (default: 30,000 tokens) to prevent unnecessary billing costs.

