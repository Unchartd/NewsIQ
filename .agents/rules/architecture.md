---
trigger: always_on
---

# architecture.md — Architecture Standards for NewsIQ

This document defines the architectural boundaries and responsibilities across the NewsIQ codebase.

## 1. Domain Segregation & Boundaries
- **Backend Service (`apps/api`)**:
  - Exposes RESTful endpoints via **FastAPI**.
  - Logic is decoupled into route handlers, services, and repositories.
  - Background workers handle asynchronous tasks (e.g., RSS ingestion) using a Redis-backed task queue.
- **AI Processing Pipeline**:
  - Modular workflows for RSS parsing, embedding, Named Entity Recognition (NER), Entity Linking, Event Extraction, and Story Clustering.
  - LLM integration is abstracted via clear interfaces, incorporating cost tracking, rate-limiting, and prompt versioning.
- **Frontend App**:
  - Responsive **React** interface styled with **Tailwind CSS**.
  - Direct database access is strictly prohibited; all state transitions must be driven by API communication.
- **Database Layer**:
  - PostgreSQL (relational structured metadata, discovery tables) with migrations managed via Alembic.
  - MongoDB (raw document storage, rich article payloads).
  - Qdrant (vector storage for embeddings, similarity queries, and clustering).
  - Redis (caching and pub/sub queues).

## 2. Communication Patterns
- All external client traffic communicates via API endpoints.
- Avoid tight coupling between services; use queues, event routers, or pub/sub patterns for pipeline staging.
- Database access should go through repository abstractions. Direct database connection pooling from business controllers is discouraged.
