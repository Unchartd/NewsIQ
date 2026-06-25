# Migration Guide — Neon + Upstash + R2 Migration

## Overview

This guide walks through migrating NewsIQ from local Docker infrastructure to
Neon PostgreSQL + Upstash Redis + Cloudflare R2. All steps are reversible.

---

## Prerequisites

- [ ] Neon account with `newsiq-prod` project created
- [ ] 3 Upstash Redis databases created (`newsiq-cache`, `newsiq-broker`, `newsiq-backend`)
- [ ] Cloudflare R2 bucket created (optional, for storage backend)
- [ ] Oracle VM accessible via SSH
- [ ] `.env.production` file populated with all credentials

---

## Step 1 — Prepare Credentials

Create `.env.production` on the Oracle VM:

```bash
ssh user@ORACLE_VM_IP
cd /opt/newsiq
cp .env.example .env.production
nano .env.production
```

Fill in:
- `DATABASE_URL` — Neon pooled endpoint
- `DATABASE_DIRECT_URL` — Neon direct endpoint
- `DATABASE_SSL=true`
- `REDIS_URL` — Upstash cache instance
- `CELERY_BROKER_URL` — Upstash broker instance
- `CELERY_RESULT_BACKEND` — Upstash backend instance
- `STORAGE_BACKEND=r2` (or `local` if skipping R2 for now)
- All AI API keys
- `SECRET_KEY` — generate with `openssl rand -hex 32`

---

## Step 2 — Test Managed Service Connectivity

Before migrating production data, verify connectivity:

```bash
# Test Neon connection
docker run --rm \
  -e DATABASE_URL="$DATABASE_URL" \
  -e DATABASE_DIRECT_URL="$DATABASE_DIRECT_URL" \
  -e DATABASE_SSL=true \
  ghcr.io/OWNER/newsiq/newsiq-api:latest \
  python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    engine = create_async_engine('$DATABASE_DIRECT_URL')
    async with engine.connect() as c:
        r = await c.execute(text('SELECT version()'))
        print('Neon connected:', r.scalar())

asyncio.run(test())
"

# Test Upstash connection
python3 -c "
import redis
r = redis.from_url('$REDIS_URL', ssl_cert_reqs=None)
print('Upstash PING:', r.ping())
"
```

---

## Step 3 — Export Local PostgreSQL Data (Optional)

If you have existing data you want to migrate:

```bash
# On Oracle VM — dump from local container
docker exec newsiq-postgres pg_dump -U newsiq newsiq > /tmp/newsiq_backup_$(date +%Y%m%d).sql

# Copy to local machine
scp user@ORACLE_VM_IP:/tmp/newsiq_backup_*.sql ./

# Import to Neon using the direct connection
psql "$DATABASE_DIRECT_URL_PSQL_FORMAT" < newsiq_backup_*.sql
```

> [!WARNING]
> The Neon connection string uses `postgresql+asyncpg://` for SQLAlchemy.
> For `psql`, use `postgresql://` instead (without `+asyncpg`).

---

## Step 4 — Run Alembic Migrations on Neon

```bash
docker run --rm \
  --env-file .env.production \
  ghcr.io/OWNER/newsiq/newsiq-api:latest \
  alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade -> 0001_initial_schema, ...
INFO  [alembic.runtime.migration] Running upgrade ... -> obs_001_foundation_observability_tables
```

---

## Step 5 — Validate Health Check Against Managed Services

```bash
# Start the prod API with managed services
docker run --rm -p 8000:8000 \
  --env-file .env.production \
  ghcr.io/OWNER/newsiq/newsiq-api:latest \
  uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal
curl http://localhost:8000/ready | python3 -m json.tool
```

Expected:
```json
{
  "status": "ready",
  "checks": {
    "database": {"status": "ok", "latency_ms": 45.2},
    "cache": {"status": "ok", "latency_ms": 12.8}
  }
}
```

---

## Step 6 — Switch Production Traffic

```bash
cd /opt/newsiq

# Stop old dev-profile services
docker compose --profile dev down

# Start prod-profile services (uses managed services)
docker compose --env-file .env.production --profile prod --profile monitor up -d

# Monitor logs
docker compose --profile prod logs -f user-api
```

---

## Step 7 — Verify Post-Migration

```bash
# All health checks
curl http://localhost:8000/health
curl http://localhost:8000/health/database
curl http://localhost:8000/health/cache
curl http://localhost:8000/health/storage

# Celery tasks running
docker compose logs -f celery-worker | head -50

# Check Neon dashboard for active connections
# Check Upstash dashboard for commands/second
```

---

## Rollback Procedure

If anything fails, rolling back takes < 2 minutes:

```bash
# Stop prod services
docker compose --profile prod down

# Restart with local services
docker compose --profile dev up -d

# No data migration required — Neon is the source of truth after Step 4
# If you need to restore from the pre-migration dump:
docker exec newsiq-postgres psql -U newsiq newsiq < /tmp/newsiq_backup_*.sql
```

---

## Rollback to Self-Hosted (Any Time)

To revert from managed services to fully self-hosted:

```bash
# Update .env.production
DATABASE_URL=postgresql+asyncpg://newsiq:newsiq@postgres:5432/newsiq
DATABASE_DIRECT_URL=postgresql+asyncpg://newsiq:newsiq@postgres:5432/newsiq
DATABASE_SSL=false
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
STORAGE_BACKEND=local

# Switch to dev profile (includes local stateful services)
docker compose --profile dev up -d
```

Zero code changes required.
