# Runbook: Wikidata API Resiliency & Troubleshooting

This runbook guides operators through monitoring, diagnosing, and maintaining the external Wikidata Entity Linker resolution pipeline under outage or degraded performance scenarios.

---

## 1. Symptoms & Alerts
- Celery worker logs show repetitive warning traces:
  `Wikidata lookup failed for <entity_name>: HTTPStatusError: 503 Service Unavailable`
- Metrics show a spike in `newsiq_crawler_http_failure_total` with status codes relating to wikidata.org.
- Entity linking tasks take longer to run, but do NOT crash. Under extreme outages, they fall back gracefully to local entity representations without raising unhandled `RetryError` exceptions.

---

## 2. Diagnostics
Check the status of Wikidata connectivity from within the running containers:

### A. Verify Public Wikidata Endpoint Connectivity
Test if the backend container can reach the Wikidata API:
```bash
docker compose exec api curl -s -I -H "User-Agent: NewsIQ/1.0 (admin@newsiq.com)" "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Google&language=en&format=json&limit=1"
```

### B. Monitor Log Warning Messages
Filter the Celery worker logs specifically for Wikidata API lookup warnings:
```bash
docker logs newsiq-celery-worker | grep -i "wikidata"
```

---

## 3. Resiliency Mechanisms & Operations

### A. Centralized HTTP Client Pool
All external requests to Wikidata share the application-level `HTTPClientPool` defined in `app/core/http_client.py`. This ensures:
- Sockets are multiplexed and reused via keepalive.
- Active connection limits are capped to prevent client port exhaustion.
- Sockets are cleanly closed on application lifecycle shutdown, preventing active socket leaks.

### B. Tenacity Retry Details
- **Max Attempts**: 3
- **Backoff**: Exponential (`multiplier=1`, `min=1`, `max=5` seconds)
- **Retry Trigger**: Any connection timeouts, DNS resolve issues, or non-200 HTTP response status codes (triggered by `response.raise_for_status()`).

### C. Graceful Fallbacks (No-Crash Guarantees)
If all 3 retry attempts fail (e.g., during a complete Wikidata outage):
1. The Tenacity `retry_error_callback` returns `[]` for `_query_wikidata_multi` and `None` for `_query_wikidata`.
2. The pipeline logs a warning and proceeds to local entity heuristics matching or LLM-driven agentic disambiguation.
3. Operation is continuous and robust; no tasks fail or require Celery queue restarts.
