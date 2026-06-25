# Docker Compose Profiles Guide

## Profiles Overview

| Profile | Services Included | Use Case |
|---|---|---|
| `dev` | Local PostgreSQL, Redis, Langfuse, APIs (with hot-reload) | Local development |
| `prod` | APIs (production mode), Celery workers | Production on Oracle VM (managed services via env) |
| `monitor` | Prometheus, Grafana | Add to any profile for observability |
| `tools` | Flower (Celery UI), pgAdmin | Add to dev for debugging |
| `admin` | Admin dashboard | Add when admin app is needed |

---

## Development (Full Local Stack)

Uses local PostgreSQL and Redis containers — no external services required.

```bash
# Start everything for development
docker compose --profile dev up

# With monitoring
docker compose --profile dev --profile monitor up

# With debugging tools
docker compose --profile dev --profile tools up

# Watch mode (auto-sync code changes)
docker compose --profile dev watch
```

**Service URLs:**
- API: http://localhost:8000
- Processing API: http://localhost:8001
- Web: http://localhost:3000
- Langfuse: http://localhost:3100
- Grafana: http://localhost:3001 (with `--profile monitor`)
- Flower: http://localhost:5555 (with `--profile tools`)
- pgAdmin: http://localhost:5050 (with `--profile tools`)

---

## Production (Managed Services)

Uses Neon + Upstash via environment variables. Local PostgreSQL/Redis containers are NOT started.

```bash
# Create .env.production with Neon + Upstash URLs
cp .env.example .env.production
# Edit .env.production with real credentials

# Start production services
docker compose --env-file .env.production --profile prod up -d

# With monitoring
docker compose --env-file .env.production --profile prod --profile monitor up -d
```

**Required env vars for prod profile:**
```bash
DATABASE_URL=postgresql+asyncpg://...neon.tech/newsiq?pgbouncer=true&sslmode=require
DATABASE_DIRECT_URL=postgresql+asyncpg://...neon.tech/newsiq?sslmode=require
DATABASE_SSL=true
REDIS_URL=rediss://:TOKEN@HOST.upstash.io:PORT
CELERY_BROKER_URL=rediss://:TOKEN@HOST2.upstash.io:PORT
CELERY_RESULT_BACKEND=rediss://:TOKEN@HOST3.upstash.io:PORT
STORAGE_BACKEND=r2
R2_ENDPOINT=https://ACCOUNT.r2.cloudflarestorage.com
R2_BUCKET=newsiq-prod
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
SECRET_KEY=<openssl rand -hex 32>
```

---

## Running Migrations

```bash
# Against Neon (from local machine)
docker run --rm \
  --env-file .env.production \
  ghcr.io/OWNER/newsiq/newsiq-api:latest \
  alembic upgrade head

# Against local DB (dev)
docker compose --profile dev run --rm user-api-dev alembic upgrade head
```

---

## Useful Commands

```bash
# Stop all services
docker compose --profile dev down

# Stop and remove volumes (DESTRUCTIVE — wipes local DB data)
docker compose --profile dev down -v

# View logs for a specific service
docker compose --profile dev logs -f celery-worker-dev

# Restart a single service
docker compose --profile dev restart user-api-dev

# Shell into the API container
docker compose --profile dev exec user-api-dev bash

# Check health of all services
curl http://localhost:8000/ready
```

---

## Service Name Reference

| Profile | User API | Processing API | Celery Worker | Celery Beat |
|---|---|---|---|---|
| `dev` | `user-api-dev` | `processing-api-dev` | `celery-worker-dev` | `celery-beat-dev` |
| `prod` | `user-api` | `processing-api` | `celery-worker` | `celery-beat` |

Note: Docker container names are the same regardless of profile (`newsiq-user-api`, `newsiq-celery-worker`, etc.).
