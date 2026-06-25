# Neon PostgreSQL Setup Guide

## Overview

NewsIQ uses [Neon](https://neon.tech) as its managed PostgreSQL provider. Neon provides:
- Serverless PostgreSQL with autosuspend (scales to zero)
- PgBouncer connection pooling
- Branching for dev/staging environments
- Free tier: 0.5 GB storage, 5 compute hours/day, 10 max connections

---

## 1. Create a Neon Project

1. Sign up at [console.neon.tech](https://console.neon.tech)
2. Create a new project named `newsiq-prod`
3. Select **PostgreSQL 17** (or latest)
4. Select the region closest to your Oracle VM

---

## 2. Get Connection Strings

In the Neon console, go to **Connection Details** for your project.

Copy **two** connection strings:

### Pooled Endpoint (for the application)
```
postgresql+asyncpg://newsiq:<password>@<region>.neon.tech/newsiq?pgbouncer=true&sslmode=require
```
→ Set as `DATABASE_URL`

### Direct Endpoint (for Alembic migrations)
```
postgresql+asyncpg://newsiq:<password>@ep-<id>.neon.tech/newsiq?sslmode=require
```
→ Set as `DATABASE_DIRECT_URL`

> [!IMPORTANT]
> Always use the **direct** (non-pooled) endpoint for Alembic. PgBouncer does not
> support the `SET` statements Alembic uses for locking.

---

## 3. Environment Variables

```bash
# .env or Coolify environment variables
DATABASE_URL=postgresql+asyncpg://newsiq:PASSWORD@ep-REGION-ENDPOINT.neon.tech/newsiq?pgbouncer=true&sslmode=require
DATABASE_DIRECT_URL=postgresql+asyncpg://newsiq:PASSWORD@ep-DIRECT-ENDPOINT.neon.tech/newsiq?sslmode=require
DATABASE_SSL=true
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=2
DB_POOL_RECYCLE=300
```

---

## 4. Run Migrations

```bash
# From the apps/api directory
DATABASE_DIRECT_URL=<neon-direct-url> alembic upgrade head
```

Or in Docker:
```bash
docker run --rm \
  -e DATABASE_DIRECT_URL=<neon-direct-url> \
  -e DATABASE_URL=<neon-pooled-url> \
  -e DATABASE_SSL=true \
  ghcr.io/OWNER/newsiq/newsiq-api:latest \
  alembic upgrade head
```

---

## 5. Connection Pool Configuration

The app is configured conservatively for Neon free tier:

| Setting | Value | Notes |
|---|---|---|
| `pool_size` | 5 | Neon free: max 10 connections total |
| `max_overflow` | 2 | Allow burst to 7 total |
| `pool_recycle` | 300 | Recycle every 5 min (Neon autosuspend) |
| `pool_pre_ping` | True | Detect dropped connections before use |
| SSL | Required | `sslmode=require` in URL |

For paid Neon plans, increase `DB_POOL_SIZE` to 15–20 and `DB_MAX_OVERFLOW` to 10.

---

## 6. Neon Branching for Dev/Staging

Create separate branches for dev and staging to isolate data:

```bash
# Install Neon CLI
npm install -g neonctl

# Create a dev branch
neonctl branches create --name=dev --project-id=<project-id>

# Get the dev branch connection string
neonctl connection-string dev
```

Use the dev branch URL in your local `.env` to avoid polluting production data.

---

## 7. Rollback to Self-Hosted PostgreSQL

```bash
# Change these env vars — no code changes required
DATABASE_URL=postgresql+asyncpg://newsiq:newsiq@selfhosted:5432/newsiq
DATABASE_DIRECT_URL=postgresql+asyncpg://newsiq:newsiq@selfhosted:5432/newsiq
DATABASE_SSL=false
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
```
