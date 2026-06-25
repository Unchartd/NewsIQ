# Upstash Redis Setup Guide

## Overview

NewsIQ uses [Upstash](https://upstash.com) as its managed Redis provider. Upstash provides:
- Serverless Redis (pay-per-request)
- TLS encrypted connections (`rediss://`)
- REST API fallback for edge environments
- Free tier: 10,000 commands/day per database

> [!IMPORTANT]
> Upstash **does not support multiple Redis database indices** (`/0`, `/1`, `/2`).
> Since the free tier only allows 1 database, you can **point all three roles (cache, broker, and backend) to the same single Upstash Redis instance (database 0)**.
> They share the database without conflict because their key namespaces (e.g. `story:*` vs Celery's queues and results) do not overlap.
> Alternatively, you can create 3 separate databases if you want separate analytics or eviction policies.

---

## 1. Create Upstash Redis Database

1. Sign up at [console.upstash.com](https://console.upstash.com)
2. Create **1 Redis database** (recommended for free tier) or **3 Redis databases**:
   - `newsiq-redis` (for shared setup) OR:
   - `newsiq-cache` → App cache (stories, trending, rate limits)
   - `newsiq-broker` → Celery task queue broker
   - `newsiq-backend` → Celery task result storage

3. Configure the database:
   - Select the region closest to your Oracle VM
   - Enable **TLS** (on by default)
   - Keep **Eviction Policy**: For a shared single database, use `noeviction` (Celery broker requires this so tasks are not evicted) or `allkeys-lru` (only if you have low cache usage). If using 3 databases, use `allkeys-lru` for cache and `noeviction` for broker/backend.

---

## 2. Get Connection Strings

For each Upstash database, go to **REST API** → **Connection details**.

The connection string format is:
```
rediss://:<PASSWORD>@<HOSTNAME>:<PORT>
```

> [!NOTE]
> The `rediss://` scheme (with double `s`) indicates TLS — this is automatic in Upstash.

---

## 3. Environment Variables

### Option A: Shared Single Upstash Redis Instance (Recommended for Free Tier)
Point all three variables to the exact same database:
```bash
# Point all three to your single Upstash Redis instance (database 0 by default)
REDIS_URL=rediss://:PASSWORD@HOSTNAME.upstash.io:PORT
CELERY_BROKER_URL=rediss://:PASSWORD@HOSTNAME.upstash.io:PORT
CELERY_RESULT_BACKEND=rediss://:PASSWORD@HOSTNAME.upstash.io:PORT
```

### Option B: 3 Separate Upstash Redis Instances
```bash
# newsiq-cache database
REDIS_URL=rediss://:PASSWORD@HOSTNAME.upstash.io:PORT

# newsiq-broker database
CELERY_BROKER_URL=rediss://:PASSWORD@HOSTNAME2.upstash.io:PORT

# newsiq-backend database
CELERY_RESULT_BACKEND=rediss://:PASSWORD@HOSTNAME3.upstash.io:PORT
```

---

## 4. TLS Configuration

The codebase automatically detects `rediss://` and enables TLS:

**`cache_service.py`** — Detects `rediss://` and creates SSL context:
```python
if url.startswith("rediss://"):
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    kwargs["ssl"] = True
```

**`celery_app.py`** — Automatically sets `broker_use_ssl` and `redis_backend_use_ssl`:
```python
if url.startswith("rediss://"):
    conf["broker_use_ssl"] = {"ssl_cert_reqs": None}
```

No manual configuration required beyond setting the `rediss://` URL.

---

## 5. Rate Limits & Capacity Planning

| Plan | Commands/day | Bandwidth | Storage | Price |
|---|---|---|---|---|
| Free | 10,000/db | 1 GB/month | 256 MB | $0 |
| Pay-as-you-go | Unlimited | Metered | 1 GB | ~$0.2/100k commands |
| Pro 2K | 2M/day | 20 GB/month | 1 GB | $20/month |

At MVP scale (100 users):
- Cache reads/writes: ~500/day → free tier sufficient
- Celery tasks: ~200/day → free tier sufficient

At 1,000 users, upgrade to pay-as-you-go (~$2–5/month per instance).

---

## 6. Rollback to Self-Hosted Redis

```bash
# Change these env vars — no code changes required
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

And start the local Redis container:
```bash
docker compose --profile dev up redis -d
```
