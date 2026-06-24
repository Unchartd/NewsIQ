# 🗺️ NewsIQ Production Hardening Implementation Plan

This document establishes the roadmap, implementation sequencing, and verification gates for the production-hardening phase of NewsIQ.

---

## 1. Roadmap & Scheduling

The remediation is split into three core phases designed to ensure zero downtime, prevent data pollution, and verify all updates against the existing test suite:

```
[Phase 1: Audits & Planning] ──► [Phase 2: Concurrency & Lock] ──► [Phase 3: Pipeline Re-ordering & Similarity Engine]
```

### Phase 1: Deliverables & Audit Docs (Prerequisite)
* **Goal**: Document system architecture, risk modeling, and technical designs.
* **Duration**: 1 Day
* **Status**: Complete (docs written in `/docs/remediation/`).

### Phase 2: Concurrency & Lock Implementation
* **Goal**: Integrate transactional advisory locks to protect clustering and merging processes from race conditions.
* **Duration**: 2 Days
* **Tasks**:
  1. Add UUID-to-bigint lock ID mapping helper.
  2. Implement `pg_advisory_xact_lock` wrapper in database session contexts.
  3. Lock `add_article_to_existing_story_if_similar` and `run_batch_clustering`.

### Phase 3: Pipeline Re-ordering & Similarity Engine Correction
* **Goal**: Restructure story updating workflow and resolve false-positive merge triggers.
* **Duration**: 2 Days
* **Tasks**:
  1. Refactor event similarity direct comparison logic (Jaccard empty sets, missing time checks).
  2. Relocate Knowledge Graph compilation and serialization to run after contradiction/difference analysis.
  3. Validate database cascade rules.

---

## 2. Verification Gates & Fallbacks

To ensure code stability, every code modification must pass through the following testing steps:

### Phase Gate 1: Syntax & Linter Validation
* Run syntax parser to ensure Python code is syntactically sound and conforms to clean formatting standards.

### Phase Gate 2: Local Docker Container Tests
* Execute the backend pytest test suite in the API container:
  ```bash
  docker compose exec -T user-api env PYTHONPATH=. pytest tests/
  ```
* All 120+ unit tests must pass before code is merged.

### Phase Gate 3: E2E Pipeline Ingestion Run
* Trigger manual ingestion of active RSS feeds via Celery workers. Verify that stories are generated successfully and Qdrant embeddings are indexed without mock fallbacks.

### Rollback Strategy
* If a database migration or lock implementation causes connection pool timeouts:
  1. Revert changes on the active branch.
  2. Fall back to standard read/write lock isolation if advisory locks lock connections indefinitely.
  3. In case of schema issues, roll back database migrations using Alembic:
     ```bash
     docker compose exec -T user-api alembic downgrade -1
     ```
