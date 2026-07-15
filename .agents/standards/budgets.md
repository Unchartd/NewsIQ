# budgets.md — Performance Budgets for NewsIQ

This document lists the specific, numeric performance budgets and thresholds required for release.

## 1. Latency Budgets (95th Percentile)
- **API Endpoints**:
  - Simple read / status endpoints: `< 100ms`.
  - Database lists / paginated search queries: `< 300ms`.
  - Write / update operations: `< 200ms`.
- **AI Pipelines**:
  - NER extraction and article parsing: `< 1.5s` per document.
  - Vector similarity search: `< 150ms`.
  - Story clustering batch execution: `< 5s` per 50 articles.
  - Summarization / Reflection synthesis: `< 10s` per story.

## 2. Memory & Resources
- **Background Worker Threads**: Max heap usage `< 512MB` per worker container.
- **Frontend Bundle Size**: Initial assets payload size `< 300KB` (gzipped).
- **Database Connection Pools**: Postgres pool maximum `< 20` active connections; Mongo pool maximum `< 50` active connections.
