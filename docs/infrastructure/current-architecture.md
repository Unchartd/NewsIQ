# Current Architecture — Pre-Migration Audit

**Audit Date:** 2026-06-25
**Status:** Pre-migration baseline

---

## Overview

NewsIQ currently runs entirely on a single Oracle VM using Docker Compose. All stateful infrastructure — PostgreSQL, Redis, Langfuse — runs in containers on the same host as compute services.

---

## Service Inventory

| Service | Container | Image | Role | Memory Est. |
|---|---|---|---|---|
| PostgreSQL 17 | `newsiq-postgres` | `postgres:17-alpine` | Primary database | ~250 MB |
| Redis 7 | `newsiq-redis` | `redis:7-alpine` | Cache + Celery broker/backend | ~50 MB |
| Langfuse DB | `newsiq-langfuse-db` | `postgres:17-alpine` | Langfuse observability store | ~150 MB |
| Langfuse | `newsiq-langfuse` | `langfuse/langfuse:2` | LLM trace UI | ~250 MB |
| pgAdmin | `newsiq-pgadmin` | `dpage/pgadmin4` | DB management UI | ~150 MB |
| Qdrant | `newsiq-qdrant` | `qdrant/qdrant` | Vector database (article embeddings) | ~200 MB |
| Meilisearch | `newsiq-meilisearch` | `getmeili/meilisearch` | Full-text story search | ~100 MB |
| FastAPI User API | `newsiq-user-api` | local build | HTTP API (port 8000) | ~300 MB |
| FastAPI Processing API | `newsiq-processing-api` | local build | Processing API (port 8001) | ~300 MB |
| Celery Worker | `newsiq-celery-worker` | local build | Background AI pipeline | ~500 MB |
| Celery Beat | `newsiq-celery-beat` | local build | Task scheduler | ~200 MB |
| Prometheus | `newsiq-prometheus` | `prom/prometheus` | Metrics collection | ~100 MB |
| Grafana | `newsiq-grafana` | `grafana/grafana` | Metrics dashboard | ~150 MB |
| **Total** | | | | **~2.7 GB** |

---

## Infrastructure Dependencies Found in Code

### PostgreSQL

| File | Usage |
|---|---|
| `app/core/database.py` | Engine creation, session factory |
| `app/core/deps.py` | `get_db()` FastAPI dependency |
| `app/workers/tasks.py` | `engine.sync_engine.dispose()` in Celery tasks |
| `alembic/env.py` | Migration runner |
| `alembic.ini` | Hardcoded URL (overridden at runtime) |
| `app/models/*.py` | All ORM models (19 tables across 3 files) |
| `app/repositories/*.py` | All data access layer code |
| `app/services/auth_service.py` | User/session DB operations |
| `app/services/admin_service.py` | Admin query operations |

**Critical issue:** `pool_pre_ping=False` will cause connection failures with Neon serverless (connections drop after autosuspend). `pool_size=20` exceeds Neon free tier.

### Redis

| File | Usage | Redis DB |
|---|---|---|
| `app/services/cache_service.py` | Story/search/trending cache | DB 0 |
| `app/core/rate_limiter.py` | Fixed-window rate limiting | DB 0 |
| `app/workers/celery_app.py` | Celery broker | DB 1 |
| `app/workers/celery_app.py` | Celery result backend | DB 2 |

**Critical issue:** Upstash does not support multiple DB indices. 3 separate Upstash instances required.

### Local Filesystem

| File | Usage |
|---|---|
| None currently | No production filesystem storage exists |

**Status:** No migration required for existing code. New `StorageProvider` interface implemented for future use.

### Session Storage

Sessions are stored in PostgreSQL (`sessions` table). JWT refresh tokens are hashed and stored in DB. No server-side session storage in Redis currently.

### Background Jobs (Celery)

| Task | Schedule | Dependencies |
|---|---|---|
| `ingest_news_task` | Every 5 min | PostgreSQL, Qdrant |
| `ingest_gnews_task` | Every 30 min | PostgreSQL, Qdrant |
| `cluster_news_task` | Every 10 min | PostgreSQL, Qdrant, Redis |
| `extract_events_task` | Every 10 min | PostgreSQL |
| `cleanup_expired_sessions_task` | Daily midnight | PostgreSQL |
| `process_hourly_digests_task` | Hourly | PostgreSQL |
| `collect_queue_metrics_task` | Every minute | Redis, PostgreSQL |

---

## Memory Impact Analysis

### Pre-migration (current)
- Stateful services: **~850 MB** (PostgreSQL + Redis + Langfuse + Langfuse DB + pgAdmin)
- Compute services: **~1.85 GB** (APIs + Workers + Qdrant + Meilisearch + Prometheus + Grafana)
- **Total: ~2.7 GB**

### Post-migration (target)
- Stateful services: **0 MB** on VM (moved to Neon + Upstash + Langfuse Cloud)
- Compute services: **~1.65 GB** (Qdrant + Meilisearch stay local, pgAdmin removed)
- **Total: ~1.65 GB — saving ~1.05 GB RAM**

---

## Migration Strategy

| Service | Strategy | Effort | Risk |
|---|---|---|---|
| PostgreSQL | Replace URL → Neon. `pool_pre_ping`, `pool_size` changes. | Low | Low |
| Redis | Replace URLs → Upstash (3 instances). TLS `rediss://` changes. | Low | Low |
| Langfuse | Switch to Langfuse Cloud. Change `LANGFUSE_HOST`. | Very Low | None |
| pgAdmin | Remove (use Neon web console instead). | None | None |
| Object Storage | New `StorageProvider` interface + R2 backend. | Medium | None (new feature) |

---

## Estimated Monthly Savings

| Resource | Before | After | Saving |
|---|---|---|---|
| Oracle VM RAM | ~2.7 GB needed | ~1.65 GB | **+1 GB headroom** |
| PostgreSQL maintenance | Manual backups, upgrades | Neon managed | **0 operational hours** |
| Redis maintenance | Manual | Upstash managed | **0 operational hours** |
| Monthly cost | ~$0 (free OCI) + time | ~$0 (free tiers) | **Same cost, less work** |
