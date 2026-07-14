# Ingestion Pipeline Architecture

This document describes the design, execution flow, and concurrency controls of the NewsIQ RSS Ingestion Pipeline.

---

## 1. Pipeline Execution Flow

The ingestion pipeline runs on a scheduled basis (via Celery Beat) or when manually triggered. The sequence of operations is as follows:

```
RSS Feed Source (rss_url)
    ↓
_fetch_feed()  [Fetch feed XML via httpx]
    ↓
_prepare_entries()  [Parse with feedparser & canonicalize URLs]
    ↓
_batch_existing_articles()  [Bulk database lookup to identify duplicates]
    ↓
_crawl_articles()  [Concurrent crawl with Semaphore concurrency limit]
    ↓
_persist_articles()  [Check content duplicates, write to DB, update Bloom Filter]
    ↓
_dispatch_discovery()  [Prioritize & enqueue candidates for Google News search discovery]
```

## 2. Ingestion Service Isolation

The ingestion flow in `IngestionService` (`app/services/ingestion_service.py`) is structured into small modular methods to maximize testability and maintainability:

- **`_fetch_feed`**: Safely retrieves the raw feed text over HTTP.
- **`_prepare_entries`**: Normalizes URLs and aligns feed entry maps.
- **`_batch_existing_articles`**: Optimizes database calls via batch SQL queries instead of N+1 SELECT statements.
- **`_crawl_articles`**: Coordinates asynchronous execution pools with rate limits.
- **`_persist_articles`**: Manages exact-content hash checks and handles database session commits.
- **`_dispatch_discovery`**: Scores new articles and launches downstream Celery search tasks.

## 3. Concurrency and Rate Limiting

The ingestion pipeline respects local server limits. The concurrency level is configured globally in `config.py` via:
`settings.CRAWLER_MAX_CONCURRENT_REQUESTS` (default: `5`).

This limits concurrent local crawler requests, preventing resource exhaustion on target domains and worker processes.
