# Operations Runbooks

This directory contains actionable step-by-step incident response procedures for NewsIQ operations.

---

## Runbook Index

| Service Affected | Runbook File | Severity | Key Objective |
| :--- | :--- | :---: | :--- |
| **PostgreSQL Database** | **[database-outage.md](file:///c:/Users/zakau/NewsIQ/docs/runbooks/database-outage.md)** | Critical | Restore relational data service, run migrations, verify backups. |
| **Redis Cache** | **[redis-failure.md](file:///c:/Users/zakau/NewsIQ/docs/runbooks/redis-failure.md)** | High | Recover cache keys, flush corrupted states, restart Celery brokering. |
| **LLM Provider APIs** | **[llm-provider-outage.md](file:///c:/Users/zakau/NewsIQ/docs/runbooks/llm-provider-outage.md)** | Medium | Adjust Gemini rate limits, check quota limits, toggle fallback models. |
| **Wikidata API Gateway** | **[wikidata-resiliency.md](file:///c:/Users/zakau/NewsIQ/docs/runbooks/wikidata-resiliency.md)** | Low | Verify connection pools, check Tenacity retry callbacks, troubleshoot DNS. |
| **Deployment System** | **[emergency-procedures.md](file:///c:/Users/zakau/NewsIQ/docs/runbooks/emergency-procedures.md)** | High | Initiate container rollbacks, recover logs, update secrets. |
