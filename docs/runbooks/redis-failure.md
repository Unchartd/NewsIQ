# Runbook: Redis Cache & Queue Failure

This runbook guides operators through diagnosing and recovering from a Redis outage, cache corruption, or queue block.

---

## 1. Symptoms & Alerts
- User authentication and token refresh operations fail with `Redis Connection Error`.
- Celery worker logs show tasks stuck in `pending` or queue lookup timeouts:
  `kombu.exceptions.OperationalError: connection to redis://redis:6379/1 failed`
- Users are logged out unexpectedly or session cookies are rejected.
- API rate-limiter denies all incoming requests or defaults to failing open.

---

## 2. Diagnostics
Perform the following checks on the host server:

### A. Check Container Health
Verify Redis service is running:
```bash
docker ps --filter name=newsiq-redis
```

### B. Ping the Redis Instance
Execute a ping test internally:
```bash
docker compose exec redis redis-cli ping
```
*Expected response:* `PONG`

### C. Inspect Memory Allocation
Check if Redis is rejecting writes due to OOM (`maxmemory` limit reached):
```bash
docker compose exec redis redis-cli info memory | grep used_memory_human
```

---

## 3. Recovery Procedures

### A. Scenario 1: Service Offline
If the Redis container has stopped or is unhealthy:
1. **Restart the container**:
   ```bash
   docker compose restart redis
   ```
2. **Force restart Celery background workers** (to restore broken connection handles):
   ```bash
   docker compose restart celery_worker celery_beat api
   ```

### B. Scenario 2: Memory Exhausted (OOM)
If Redis is refusing commands with `OOM command not allowed when used memory > 'maxmemory'`:
1. **Temporarily clear non-essential caches** (trending lists, story details) to free memory without dropping active user sessions:
   ```bash
   docker compose exec redis redis-cli -n 0 SCAN 0 MATCH "story:*" | xargs -r docker compose exec redis redis-cli -n 0 DEL
   docker compose exec redis redis-cli -n 0 SCAN 0 MATCH "trending:*" | xargs -r docker compose exec redis redis-cli -n 0 DEL
   ```
2. **Increase memory limit** or verify the eviction policy is set to `volatile-lru` in `redis.conf`.

### C. Scenario 3: Corrupt Session Cache or Poison Queue
If background queue processing is blocked by a corrupted payload or rate limit lock:
1. **Flush active Celery message queues** (warning: this will drop pending crawler/clustering tasks, but will not impact session cache):
   ```bash
   # Flush DB 1 (Broker Queue) and DB 2 (Result Store)
   docker compose exec redis redis-cli -n 1 FLUSHDB
   docker compose exec redis redis-cli -n 2 FLUSHDB
   ```
2. **Full Cache Flush (Emergency Only)**: If session states are corrupted, clear DB 0.
   > [!CAUTION]
   > Running `FLUSHDB` on Database 0 will immediately terminate all active user sessions globally, forcing every user to re-authenticate.
   ```bash
   docker compose exec redis redis-cli -n 0 FLUSHDB
   ```
3. **Restart the Celery containers**:
   ```bash
   docker compose restart celery_worker celery_beat
   ```

---

## 4. Verification Checklist
- [ ] `redis-cli ping` returns `PONG`.
- [ ] Celery worker logs show task discovery and execution loops.
- [ ] Authenticated actions (e.g., loading personalized feeds) execute without throwing errors.
