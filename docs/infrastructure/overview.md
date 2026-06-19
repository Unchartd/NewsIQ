# Infrastructure & Deployment

This document details the Docker orchestration, database dependencies, background task schedules, caching layers, and production scaling configurations of NewsIQ.

---

## 1. Local Development Topology

The entire application runs in a containerized environment configured via [docker-compose.yml](file:///c:/Users/zakau/NewsIQ/docker-compose.yml). 

```mermaid
graph TD
    Client[Browser (Port 3000)] --> Web[Next.js App 'web']
    Web --> API[FastAPI Server 'api' (Port 8000)]
    
    API --> Postgres[(PostgreSQL 17)]
    API --> Redis[(Redis 7)]
    API --> Qdrant[(Qdrant Vector DB)]
    API --> Meilisearch[(Meilisearch)]
    
    CeleryWorker[Celery Worker] --> Redis
    CeleryWorker --> Postgres
    CeleryWorker --> Qdrant
    CeleryWorker --> Meilisearch
    
    CeleryBeat[Celery Beat] --> Redis
```

---

## 2. Docker Services Configuration

The NewsIQ deployment is partitioned into nine logical containers:

| Service Name | Container Name | Image / Source | Internal Port | External Port | Volumes / Data Persistence |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `postgres` | `newsiq-postgres` | `postgres:17-alpine` | `5432` | `5432` | `postgres_data` |
| `pgadmin` | `newsiq-pgadmin` | `dpage/pgadmin4` | `80` | `5050` | None |
| `redis` | `newsiq-redis` | `redis:7-alpine` | `6379` | `6379` | `redis_data` |
| `qdrant` | `newsiq-qdrant` | `qdrant/qdrant:latest` | `6333`, `6334` | `6333`, `6334` | `qdrant_data` |
| `meilisearch` | `newsiq-meilisearch` | `getmeili/meilisearch` | `7700` | `7700` | `meilisearch_data` |
| `api` | `newsiq-api` | `./apps/api/Dockerfile` | `8000` | `8000` | Bind-mounted host files |
| `celery_worker`| `newsiq-celery-worker` | `./apps/api/Dockerfile` | N/A | N/A | Bind-mounted host files |
| `celery_beat` | `newsiq-celery-beat` | `./apps/api/Dockerfile` | N/A | N/A | Bind-mounted host files |
| `web` | `newsiq-web` | `./apps/web/Dockerfile.dev`| `3000` | `3000` | Bind-mounted host files |

---

## 3. Caching & Message Brokering (Redis)

NewsIQ separates caching, messaging, and Celery states by utilizing Redis database partitioning:

- **Database `0` (`REDIS_URL`)**: Core application cache and user session tracking (namespaces `session:*`, `story:*`, `trending:*`, `rate_limit:*`).
- **Database `1` (`CELERY_BROKER_URL`)**: Message broker queue for Celery.
- **Database `2` (`CELERY_RESULT_BACKEND`)**: Task execution state results store.

---

## 4. Background Workers & Celery Beat Schedule

Background tasks are managed by [celery_app.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/workers/celery_app.py) and executed by `celery_worker`. The orchestration schedule is maintained by `celery_beat` with the following active schedules:

| Task Identifier | Celery Beat Name | Interval / Cron | Purpose |
| :--- | :--- | :---: | :--- |
| `app.workers.tasks.ingest_news_task` | `ingest-rss-news-every-5-minutes` | `*/5 * * * *` | Queries and parses RSS XML feeds across all active publishers. |
| `app.workers.tasks.ingest_gnews_task` | `ingest-gnews-every-30-minutes` | `*/30 * * * *` | Pulls international news articles categorized by topic. |
| `app.workers.tasks.cluster_news_task` | `cluster-news-every-10-minutes` | `*/10 * * * *` | Clusters unassigned article vectors into new news stories. |
| `app.workers.digest_tasks.process_hourly_digests_task` | `process-hourly-digests-hourly` | `0 * * * *` | Dispatches subscription newsletter updates to premium users. |
| `app.tasks.cleanup_sessions.cleanup_expired_sessions_task` | `cleanup-expired-sessions-daily` | `0 0 * * *` | Housekeeping task to delete expired refresh session logs. |

---

## 5. Production Scaling Guidelines

When transitioning from the development Docker Compose structure to AWS ECS, Kubernetes, or Google Cloud Run, consider the following parameters:

1. **State Partitioning**: Redis cache/session and broker/results databases should be moved to managed services (e.g. AWS ElastiCache for Redis) rather than single-container instances.
2. **PostgreSQL**: Migrate the alpine postgres container to Amazon RDS (PostgreSQL 17) or Google Cloud SQL with Multi-AZ replica failover enabled.
3. **Task Concurrency**: Celery workers are set to `--concurrency=2` locally to limit concurrent LLM API calls and keep Gemini rate limits stable. Scale this value up ONLY after obtaining Gemini API pay-as-you-go tiers.
4. **Volume Persistence**: Ensure the `qdrant_data` and `meilisearch_data` volumes use high-IOPS persistent storage classes (such as AWS EBS GP3) to prevent vector storage latency bottlenecks.
