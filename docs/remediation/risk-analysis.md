# ⚠️ NewsIQ Risk Analysis & Threat Modeling

This document maps out the system risks, failure modes, and security vulnerabilities identified in the NewsIQ ingestion, clustering, and summarization pipelines, alongside their corresponding remediation strategies.

---

## 1. Concurrency & Locking Bottlenecks

### Risk: Concurrent Story Merging Race Conditions
* **Mechanism**: Multiple Celery tasks running event extraction on articles from the same news event attempt to merge their respective articles into a single story cluster concurrently. Both tasks retrieve the story, calculate similarity, determine it should merge, and insert a new `StoryArticle` record.
* **Impact**: Duplicated story data, corrupt knowledge graphs, and split timelines where half the articles are associated with one story entity and the other half are orphaned or linked to duplicate stories.
* **Severity**: **Critical**
* **Remediation**: Implement PostgreSQL transaction-bound advisory locks (`pg_advisory_xact_lock`) on the target `story_id` or a global lock during clustering.

### Risk: Database Lock Escalation & Deadlocks
* **Mechanism**: If we lock articles and stories out of order (e.g., Task A locks Article 1 then Story A; Task B locks Story A then Article 1), a deadlock will occur in PostgreSQL.
* **Impact**: Halted celery tasks, database connection pool exhaustion, and pipeline timeouts.
* **Severity**: **High**
* **Remediation**: Enforce strict locking order hierarchy (e.g., always acquire advisory locks on story UUIDs sorted lexicographically).

---

## 2. Similarity Engine Vulnerabilities

### Risk: Empty Set False-Positive Story Merges (Issue 8)
* **Mechanism**: In `_compute_event_similarity_direct`, Jaccard actor and target similarities default to `1.0` when both comparison sets are empty (e.g., when NLP parser fails to extract actors or targets). 
* **Impact**: Unrelated articles containing no actors or targets are clustered into a single massive story, causing severe data pollution.
* **Severity**: **High**
* **Remediation**: Force Jaccard similarity to `0.0` if either set is empty.

### Risk: High Similarity Mappings on Missing Event Times (Issue 10)
* **Mechanism**: When event times are missing, time similarity defaults to `0.8`, which artificially inflates overall similarity scores and forces merges of temporally distant events.
* **Impact**: Articles representing historical events or future projections are merged into current news stories.
* **Severity**: **High**
* **Remediation**: Reduce missing time similarity to `0.5`, same-day to `1.0`, and different-day to `0.0`.

---

## 3. Data Integrity & Loss Risks

### Risk: Orphaned Database Records on Story Re-generation
* **Mechanism**: The original `generate_story_content` method cleared sub-tables using SQLAlchemy collection `.clear()` queries. If transactions roll back, database sessions can lose track of these relationships, creating orphaned rows.
* **Impact**: Database bloat and foreign key constraint violations.
* **Severity**: **Medium**
* **Remediation**: Replace collection clear commands with explicit SQL `DELETE` queries targeting the exact parent `story_id`.

---

## 4. API Rate Limiting & Gateway Cascades

### Risk: Rate-Limit Key Cooldown Loops
* **Mechanism**: Under heavy concurrent article clustering, LLM gateway clients exhaust free-tier Gemini and Groq API quotas. The request manager loops indefinitely trying other keys, leading to thread locking.
* **Impact**: Worker exhaustion and crash cascades.
* **Severity**: **Critical**
* **Remediation**: Integrate backoff retry delays and key cooldown sleep limits (max 20 seconds) directly inside the request manager.

---

## 5. Summary Matrix of Risk Remediation

| Risk Domain | Risk Event | Severity | Probability | Proposed Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **Concurrency** | Concurrent story updates | Critical | High | PostgreSQL Transaction Advisory Locks |
| **Similarity** | Empty actor/target merge | High | Medium | Tight Jaccard constraints & zero-default |
| **Similarity** | Missing event time merges | High | High | Strict date matching: 1.0 (same) / 0.0 (diff) / 0.5 (missing) |
| **Integrity** | Orphaned sub-table rows | Medium | Low | Explicit SQL Delete statements in transaction |
| **Gateway** | API key exhaust cascades | High | High | Non-blocking key cooldown sleeps & mock removal |
