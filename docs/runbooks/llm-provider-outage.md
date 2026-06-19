# Runbook: LLM Provider API Outage Recovery

This runbook guides operators through managing timeouts, rate limits, and quota exhaustion when communicating with Google Gemini or OpenAI API endpoints.

---

## 1. Symptoms & Alerts
- Celery worker logs show repetitive warning traces:
  `google.genai.errors.APIError: [429] Resource has been exhausted` or
  `openai.RateLimitError: Rate limit exceeded`
- Stories are created with headlines starting with `[Mock]`, indicating fallback mechanisms have engaged due to API errors.
- Synthesis tasks take excessive time to complete, holding up the Celery task queue.

---

## 2. Diagnostics
Check the status of the AI services and active configurations:

### A. Monitor Celery Worker Logs
Look for specific API error codes (429, 401, 503, or Read Timeout):
```bash
docker logs -f newsiq-celery-worker
```

### B. Verify Model Configs
Check the active models and variables in the running container:
```bash
docker compose exec api env | grep -E "(MODEL|API_KEY)"
```

### C. Test Public Endpoint Connections
Verify if the server can resolve and connect to Google and OpenAI gateways:
```bash
docker compose exec api curl -s -I https://generativelanguage.googleapis.com
docker compose exec api curl -s -I https://api.openai.com
```

---

## 3. Mitigation & Recovery Procedures

### A. Scenario 1: Gemini 429 / Resource Exhausted (Free Tier Limits)
If you exceed free-tier limits (typically 15 RPM for text-embedding or 10 RPM for synthesis):
1. **Reduce Celery Worker Concurrency**: Edit the worker start command in `docker-compose.yml` to limit concurrent API connections:
   ```yaml
   command: celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=1
   ```
2. **Increase Throttling Sleep Interval**: Edit `app/services/ai_service.py` to increase `_SYNTHESIS_MIN_INTERVAL_S` (e.g., from `8.0s` to `12.0s`).
3. **Verify Tenacity Jitter Back-off**: Tenacity is configured to retry with exponential back-off (up to 30 seconds). Allow workers to process tasks slowly rather than terminating the queue.

### B. Scenario 2: API Keys Invalid or Expired (401 Unauthorized)
If logs indicate authentication failures:
1. **Verify keys in `.env`**: Make sure `GEMINI_API_KEY` and `OPENAI_API_KEY` are correct.
2. **Update keys on the fly**:
   - Edit `.env` with new keys.
   - Restart API and Celery workers to load new environment parameters:
     ```bash
     docker compose up -d api celery_worker celery_beat
     ```

### C. Scenario 3: Global Gemini API Outage (503 Service Unavailable)
If Google Gemini is down globally:
1. **Check OpenAI Fallback Status**: Verify that a valid `OPENAI_API_KEY` is specified in the environment. The backend will automatically fall back to OpenAI `gpt-4o-mini` if Gemini is unavailable.
2. **Validate Mock Generation**: If both providers are offline, the system will fall back to deterministic mocks. The front-end will display `[Mock] Headline` values. This keeps the application running while you resolve the API outage.
