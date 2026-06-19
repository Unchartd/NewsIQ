# Database Infrastructure Overview

NewsIQ relies on a relational primary store (PostgreSQL 17) and an in-memory session and cache broker (Redis).

---

## 1. Storage Component Choices

### A. Primary Database: PostgreSQL 17
- **Acids Compliance**: Secures transactions across users, preferences, bookmarks, and consent audit logs.
- **JSONB Support**: Utilized for storing key-fact arrays, source focus metrics, and custom UI preferences without schemas drift.
- **Relational Integrity**: Strict foreign key cascades govern deletions (e.g. cascading deletes for bookmarks and sessions when an account is scrubbed).

### B. In-Memory Cache: Redis 7
- **Session Lookup**: Caches token hashes for rotating refresh validations, protecting primary databases from auth overhead.
- **Trending Feed Cache**: Caches list payloads for trending news feeds per category, expiring in 5 minutes.
- **Message Broker**: Serves as the transport queue broker for Celery worker processes.

---

## 2. Entity Relationship Map

```text
  +-------------------+        +--------------------+
  |      users        |1------1|  user_preferences  |
  +--------+----------+        +--------------------+
           |1
           |
           +-----+-----------+------------------+
           |*    |*          |*                 |*
  +--------v-----+--+  +-----v--------+  +------v--------+  +---------------v----+
  |   bookmarks     |  |   sessions   |  | user_categories|  | consent_preferences|
  +--------+--------+  +--------------+  +---------------+  +--------------------+
           |*
           |
  +--------v-----+--+        +--------------------+
  |     stories     |1------*|story_timelineevents|
  +--------+--------+        +--------------------+
           |1
           |
           +-----+-------------------+
           |*                        |*
  +--------v--------+      +---------v----------+
  |  story_articles |      |  story_differences |
  +--------+--------+      +---------+----------+
           |*                        |*
  +--------v--------+                |
  |    articles     |*               |
  +--------+--------+                |
           |*                        |
  +--------v--------+                |
  |     sources     |1<--------------+
  +-----------------+
```

---

## 3. Database Migration Workflow (Alembic)

Database schema versions are managed sequentially using Alembic. 

### A. Key Commands

1. **Verify Current Version**:
   ```bash
   docker compose exec api alembic current
   ```
2. **Apply Outstanding Migrations**:
   ```bash
   docker compose exec api alembic upgrade head
   ```
3. **Generate New Auto-Migration**:
   ```bash
   docker compose exec api alembic revision --autogenerate -m "description of changes"
   ```
4. **Rollback Last Migration**:
   ```bash
   docker compose exec api alembic downgrade -1
   ```

### B. Discovery Configuration
Alembic migrations import `Base` from `app.core.database` and all entity modules from `app.models.__init__.py` to enable `--autogenerate` comparisons against active PostgreSQL catalogs.
