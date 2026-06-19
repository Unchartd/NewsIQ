# Runbook: Database Outage Recovery

This runbook guides operators through diagnosing and recovering from a PostgreSQL primary database outage or connection starvation event.

---

## 1. Symptoms & Alerts
- API requests fail globally returning HTTP `500 Internal Server Error`.
- Uvicorn logs show:
  `sqlalchemy.exc.OperationalError: (asyncpg.exceptions.CannotConnectNowError)` or
  `TimeoutError: [Errno 110] Connection timed out`
- Next.js frontend redirects authenticated users to error pages due to token refresh failures.

---

## 2. Diagnostics
Run the following commands on the host machine to locate the failure point:

### A. Check Container Status
Verify if the `postgres` container is running and healthy:
```bash
docker ps --filter name=newsiq-postgres
```

### B. Inspect PostgreSQL Logs
Retrieve the last 100 log lines to check for memory exhaustion (OOM), disk capacity warnings, or corrupt blocks:
```bash
docker logs --tail 100 newsiq-postgres
```

### C. Test Port Connection
Verify the network listener is active on port `5432`:
```bash
docker compose exec api pg_isready -h postgres -U newsiq
```

---

## 3. Recovery Procedures

### A. Scenario 1: Container Crashed (Stopped)
If the container stopped unexpectedly due to resource limits (OOM):
1. **Restart the container**:
   ```bash
   docker compose start postgres
   ```
2. **Verify health status**:
   ```bash
   docker ps --filter name=newsiq-postgres
   ```
   *(Wait 10 seconds for the health check to switch to `healthy`).*

### B. Scenario 2: Connection Pool Starvation
If the database is active but rejecting connections with `Too many clients`:
1. **Restart Uvicorn and Celery processes** to drop orphaned connections:
   ```bash
   docker compose restart api celery_worker
   ```
2. **Increase pool sizes** in your environment configurations (e.g. increase `SQLALCHEMY_POOL_SIZE` or modify PostgreSQL `max_connections` inside `postgresql.conf`).

### C. Scenario 3: Database Corruption or Data Loss
If database files are corrupted, restore from the last daily pg_dump backup:
1. **Stop active services** writing to the database:
   ```bash
   docker compose stop api celery_worker celery_beat
   ```
2. **Drop and recreate the database**:
   ```bash
   docker compose exec postgres dropdb -U newsiq newsiq
   docker compose exec postgres createdb -U newsiq -O newsiq newsiq
   ```
3. **Restore schema and data**:
   ```bash
   docker compose exec -T postgres psql -U newsiq -d newsiq < /path/to/backups/newsiq_latest_backup.sql
   ```
4. **Run migrations to catch up**:
   ```bash
   docker compose exec postgres alembic upgrade head
   ```
5. **Restart all containers**:
   ```bash
   docker compose start
   ```

---

## 4. Verification Checklist
- [ ] `docker ps` reports `newsiq-postgres` status as `healthy`.
- [ ] API gateway log shows successful database connection pool initialization.
- [ ] Endpoint `/api/v1/health` returns status code `200 OK`.
- [ ] pgAdmin portal is accessible at `http://localhost:5050`.
