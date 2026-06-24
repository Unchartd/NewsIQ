# 🔍 NewsIQ Architecture Remediation Findings

This document summarizes the architectural findings and structural issues identified during the system-hardening audit of the NewsIQ platform.

---

## 1. Modular Architecture & Core Pipelines

The NewsIQ system follows a pipeline-based architecture for processing crawled news articles and building coherent, multi-source news stories:

```
Ingestion (RSS/GNews) 
       ↓
Article Insertion (PostgreSQL)
       ↓
Event & Entity Extraction (spaCy / LLM Agent)
       ↓
Article Embedding Generation (OpenAI / Gemini / Cohere)
       ↓
Vector DB Upsert (Qdrant)
       ↓
Story Clustering (Incremental Vector Search / Batch HDBSCAN)
       ↓
Multi-Signal Similarity Gate (Direct Jaccard & Time Check)
       ↓
AI Verification (Agno Agent)
       ↓
Story Merging / Creation (PostgreSQL)
       ↓
Timeline, Contradiction, & Difference Analysis (Sub-tables)
       ↓
Knowledge Graph (KG) Construction & Serialization
       ↓
KG-Grounded Summary Generation (Gemini / Claude / GPT)
       ↓
Summary Reflection & Verification (Agno Agent)
       ↓
Meilisearch Indexing & Cache Invalidation (Redis)
```

### Key Structural Issues

1. **Circular Import Workarounds**:
   In `app/workers/tasks.py` and `app/services/clustering_service.py`, circular dependencies forced the lazy import of services inside task function bodies (e.g., `from app.services.clustering_service import clustering_service`). 
   * *Remediation*: Extract shared interface definitions or model dependencies into a standalone module, or leverage Dependency Injection patterns via FastAPI and Celery.

2. **Decoupled Data Pipeline Sequence**:
   The Knowledge Graph serialization ran too early in the processing queue. Story metadata was updated in Qdrant and summaries generated without guaranteeing the KG, contradiction, and difference engines finished transaction commits.
   * *Remediation*: Reorder pipeline tasks to ensure sub-table serialization commits first, followed by KG compilation, summarization, reflection, and indexing.

---

## 2. Ingestion & Extraction Gaps

1. **Sequential Source Crawling**:
   In `ingestion_service.py`, the ingestion worker fetched RSS feeds sequentially. For 100+ active news feeds, this blocked Celery worker threads for prolonged periods.
   * *Remediation*: Refactor crawling to run concurrently using `asyncio.gather` with a bounded semaphore to prevent socket exhaustion.

2. **Fragile Timeline Date Extraction**:
   Event timestamps returned by LLM extraction often diverged from ISO-8601 formatting (e.g., `"08:00 AM UTC"`, `"yesterday"`). The date parser attempted strict `datetime.fromisoformat()` parsing, throwing exceptions and defaulting event times to `None`.
   * *Remediation*: Introduce a robust date parsing utility using `dateutil.parser` or regex-based normalizers to guarantee clean datetime conversions before storage.

---

## 3. Database Querying & N+1 Performance Issues

1. **Database Session `MissingGreenlet` Errors**:
   SqlAlchemy models frequently triggered `MissingGreenlet` async exceptions in background workers. This occurred because lazy-loaded relationships (such as `story.category` during multi-signal merge verification, and `story.metrics` in trending score calculations) were accessed outside of an active database query transaction.
   * *Remediation*: Force eager loading (`selectinload(Story.category)`, `selectinload(Story.metrics)`) on all queries returning story records in clustering services.

2. **N+1 Queries in Stories List**:
   Retrieving a list of stories triggered independent queries to load original articles, categories, and metrics.
   * *Remediation*: Modify the stories API list query to join and eagerly load `StoryArticle`, `Article`, and `StoryMetric` records.

3. **Inefficient Table Counting**:
   The `compute_trending_score` function executed a full `SELECT` query of all `StoryArticle` relations matching a story ID to count rows.
   * *Remediation*: Replace with `select(func.count(StoryArticle.article_id))` to execute counting on the database side.

---

## 4. Observability & Error Hardening

1. **Silent Fallback to Mock Data**:
   On LLM key failures or rate limits, services returned mock placeholder headlines (e.g., `[Mock] Major News Event`) and zero-filled embedding arrays. This masked upstream issues and contaminated database collections.
   * *Remediation*: Remove mock fallbacks in non-testing environments. Force tasks to fail explicitly and register failures in the database.

2. **Absence of Centralized Error Tracking**:
   Pipeline exceptions were logged to standard output, making real-time error aggregation and debugging impossible.
   * *Remediation*: Implement a dedicated `pipeline_failures` database table and expose SRE dashboard routes.

---

## 5. Security & Privilege Gaps

1. **Admin Escalation Vulnerability**:
   The `update_profile` endpoint allowed any authenticated user to update their role to `"admin"` by sending `"subscription_plan": "enterprise"`.
   * *Remediation*: Strip roles and subscription parameters from public user update schemas, exposing them only via secure admin endpoints.

2. **Plaintext Storage of Client Secrets**:
   Third-party OAuth client tokens and API configurations were written to database columns in plaintext.
   * *Remediation*: Implement symmetric encryption (AES-256 via Fernet) for all credentials at rest.
