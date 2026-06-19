# Runbook: Emergency Procedures & Rollbacks

This runbook details how to handle security emergencies (such as leaked credentials) and execute emergency code or database rollbacks on production clusters.

---

## 1. Credentials Leaked / Secrets Rotation

If the server's `SECRET_KEY`, database credentials, or AI API keys are compromised, follow these procedures:

### Step 1: Update Environment Configs
1. Open the active `.env` configuration file on the production environment.
2. Generate a new cryptographically secure `SECRET_KEY`:
   ```bash
   openssl rand -hex 32
   ```
3. Update any compromised API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.) or PostgreSQL credentials.

### Step 2: Flush Cached Sessions
Changing the `SECRET_KEY` makes existing JWT access and refresh tokens invalid because the signature verification checks will fail. To ensure clean system states:
1. **Flush active Redis sessions**:
   ```bash
   docker compose exec redis redis-cli -n 0 FLUSHDB
   ```
2. **Clear Postgres session database logs**:
   ```bash
   docker compose exec postgres psql -U newsiq -d newsiq -c "DELETE FROM sessions;"
   ```

### Step 3: Restart Services
Force restart all API gateways and Celery workers to pick up the updated keys:
```bash
docker compose up -d --force-recreate api celery_worker celery_beat
```

---

## 2. Emergency Application Rollbacks

If a bad code deployment gets merged and breaks core production features:

### A. Code Rollback
1. **Find the last stable git tag**:
   ```bash
   git tag -l "v*"
   ```
2. **Checkout the last stable version branch/tag** (e.g. `v1.7.0`):
   ```bash
   git checkout tags/v1.7.0
   ```
3. **Rebuild and restart containers**:
   ```bash
   docker compose up -d --build
   ```

### B. Database Migration Rollback (Alembic)
If the bad deployment included a database schema migration that must be reverted:
1. **Identify current database revision**:
   ```bash
   docker compose exec api alembic current
   ```
2. **Locate the stable target revision ID** in `apps/api/alembic/versions/` (e.g., `a4b2c8...`):
3. **Revert the database schema**:
   ```bash
   docker compose exec api alembic downgrade a4b2c8
   ```
4. **Revert code deployment** (follow Code Rollback steps above) and confirm the running code version matches the downgraded database schema version.

---

## 3. Local Development Fresh Reset
If the local Docker environment becomes unresponsive or data is in a corrupted state:
> [!WARNING]
> The following command deletes all local database volumes. All local test articles, users, and credentials will be lost.
```bash
# Stop all services and delete persistent volumes
docker compose down -v

# Rebuild and launch containers in detached mode
docker compose up -d --build
```
*(Alembic will automatically execute on start and rebuild database tables from scratch).*
