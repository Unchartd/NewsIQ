# API Key Pools, Rotation, and Cooldowns

NewsIQ manages quota constraints and high-availability requirements via a dynamic provider key pool and routing system.

## Comma-Separated Key Rotation

API keys are loaded from environment variables (e.g. `GEMINI_API_KEY_SYNTH`, `OPENAI_API_KEY`, `GROQ_API_KEY`). If multiple keys are provided as comma-separated lists, the gateway loads them into the `APIKeyPool`:

```bash
# Example env configuration
GEMINI_API_KEY_SYNTH="key_alpha,key_beta,key_gamma"
```

The router selects keys in a round-robin/least-loaded fashion, spreading request quotas uniformly.

## Cooldown Mechanics

Key health is managed dynamically by the `HealthMonitor` in [health_monitor.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/llm_gateway/health_monitor.py):

1. **Quota Outages (HTTP 429 / RESOURCE_EXHAUSTED)**:
   * Triggers a **60-second cooldown** on the specific key.
   * The router avoids this key until `utcnow() > cooldown_until`.
2. **Authentication Errors (HTTP 401 / Forbidden)**:
   * Immediately flags `key.healthy = False`, disabling the key from the active pool until a system restart or manual intervention occurs.
3. **Transient Failures (Timeouts, Network Glitches)**:
   * Places the key on a short **15-second cooldown**.
   * If a key experiences **3 consecutive transient failures**, it is marked unhealthy (`healthy = False`).

## Sliding-Window Rate Limiting

The `RateLimitManager` tracks request rates using Redis sliding windows:

* **RPM (Requests Per Minute)**: Sorted set tracking timestamps of requests made in the last 60 seconds.
* **RPD (Requests Per Day)**: Sorted set tracking timestamps in the last 86,400 seconds.

If Redis is down or unavailable, the rate limiter falls back to an in-memory dictionary cache to prevent downstream rate-limit errors.
