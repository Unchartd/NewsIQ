# 🔒 NewsIQ Concurrency & Advisory Lock Specification

This document details the design and implementation of PostgreSQL transaction-bound advisory locks to prevent concurrent write collisions during article clustering and story updates.

---

## 1. Why Advisory Locks?

In high-concurrency event ingestion pipelines, multiple worker nodes or threads frequently attempt to process articles belonging to the same news event simultaneously. Standard table-level locking (`SELECT ... FOR UPDATE`) is highly prone to deadlocks and degrades throughput.

Advisory locks in PostgreSQL provide a lightweight, application-defined locking mechanism:
* **Transaction Scope**: By using `pg_advisory_xact_lock`, locks are automatically released upon transaction commit or rollback, eliminating the risk of dangling locks.
* **Granular Locking**: Locks are bound to specific entity IDs rather than whole tables or pages.
* **Low Overhead**: Lock state is held in PostgreSQL shared memory rather than database pages, avoiding disc I/O.

---

## 2. Converting UUIDs to Bigint Lock IDs

PostgreSQL advisory locks accept either a single 64-bit signed integer (`bigint`) or two 32-bit integers. Since NewsIQ uses 128-bit UUIDs for primary keys, we must fold UUIDs into signed 64-bit integers.

```python
import uuid

def uuid_to_advisory_lock_id(u: uuid.UUID) -> int:
    """Fold a 128-bit UUID into a signed 64-bit integer lock ID."""
    val = u.int
    # XOR the upper 64 bits with the lower 64 bits to preserve entropy
    upper = val >> 64
    lower = val & 0xffffffffffffffff
    lock_id = (upper ^ lower) & 0xffffffffffffffff
    
    # Cast to a signed 64-bit integer (-2^63 to 2^63 - 1)
    if lock_id >= 0x8000000000000000:
        lock_id -= 0x10000000000000000
        
    return lock_id
```

While folding 128 bits into 64 bits introduces a mathematical possibility of collisions, a collision in advisory locking simply results in temporary, safe serialization of two unrelated operations (no data corruption occurs).

---

## 3. Protecting the Clustering Pipeline

### 3.1 Incremental Clustering Locks
When a new article is matched to an existing story via Qdrant cosine similarity, the worker must acquire an advisory lock on the candidate story ID prior to performing similarity validation and merging:

```python
# Convert story UUID to advisory lock ID
lock_id = uuid_to_advisory_lock_id(story_id)

# Acquire transaction-bound advisory lock
await session.execute(
    text("SELECT pg_advisory_xact_lock(:lock_id)"),
    {"lock_id": lock_id}
)
```

This prevents other threads from concurrently modifying the same story structure.

### 3.2 Batch Clustering Lock
To prevent multiple scheduled Celery beat workers from running `run_batch_clustering` concurrently, we enforce a global advisory lock using a static bigint identifier (e.g., `888888888`):

```python
GLOBAL_CLUSTERING_LOCK_ID = 888888888

# Acquire global batch clustering lock
await session.execute(
    text("SELECT pg_advisory_xact_lock(:lock_id)"),
    {"lock_id": GLOBAL_CLUSTERING_LOCK_ID}
)
```
If a second batch task attempts to run, it will block until the active batch finishes.
