---
trigger: always_on
---

# database.md — Database Coding Rules for NewsIQ

These rules govern the use, migration, and optimization of relational, document, and vector databases.

## 1. Schema & Migrations
- **Alembic (PostgreSQL)**: Every relational schema change must be accompanied by an Alembic migration. Implement distinct `upgrade()` and `downgrade()` methods, ensuring no data-destructive operations execute without backup verification.
- **Aggregation Segregation**: Keep heavy database aggregation queries in dedicated repository classes. Never mix query construction with route handlers or domain rules.

## 2. Vector DB & Cache Optimization
- **Similarity Thresholds**: Always specify similarity score thresholds when querying Qdrant to filter low-confidence matching documents.
- **Eviction Policies (Redis)**: Configure specific Time-To-Live (TTL) targets for all cached keys, preventing memory saturation and maintaining a clean cache state.
