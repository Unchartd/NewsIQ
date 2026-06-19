# NewsIQ Technical Documentation Hub

Welcome to the central documentation index for NewsIQ. This portal outlines system designs, implementation patterns, operations runbooks, and compliance architecture across the NewsIQ codebase.

---

## 🗺️ Documentation Map

### 1. [System Architecture](file:///c:/Users/zakau/NewsIQ/docs/architecture/system-overview.md)
Detailed breakdowns of the platform's distributed layout, components, and responsibilities:
- **[System Overview](file:///c:/Users/zakau/NewsIQ/docs/architecture/system-overview.md)**: Global system layout and components.
- **[Frontend Architecture](file:///c:/Users/zakau/NewsIQ/docs/architecture/frontend-architecture.md)**: App Router, state managers, and hook lifecycle.
- **[Backend Architecture](file:///c:/Users/zakau/NewsIQ/docs/architecture/backend-architecture.md)**: FastAPI routers, dependencies, and patterns.
- **[Event Flow & Pipelines](file:///c:/Users/zakau/NewsIQ/docs/architecture/event-flow.md)**: sequence charts of background worker pipelines.
- **[Data Flow & Ingestion](file:///c:/Users/zakau/NewsIQ/docs/architecture/data-flow.md)**: Path of crawled stories to final vector clusters.
- **[Dependency Graph](file:///c:/Users/zakau/NewsIQ/docs/architecture/dependency-graph.md)**: Imports and module boundaries.

### 2. [API Reference](file:///c:/Users/zakau/NewsIQ/docs/api/overview.md)
Manual technical specification for all REST API endpoints:
- **[API Overview](file:///c:/Users/zakau/NewsIQ/docs/api/overview.md)**: Base URL, response shapes, pagination, and error codes.
- **[Authentication API](file:///c:/Users/zakau/NewsIQ/docs/api/auth.md)**: JWT logins, token refreshes, and OAuth.
- **[Users & Accounts API](file:///c:/Users/zakau/NewsIQ/docs/api/users.md)**: Registration, settings updates, and GDPR erasures.
- **[Stories & Timelines API](file:///c:/Users/zakau/NewsIQ/docs/api/stories.md)**: Story lists, summaries, timelines, and search.
- **[Sources & Publishers API](file:///c:/Users/zakau/NewsIQ/docs/api/sources.md)**: Publisher metadata and original articles.
- **[Consent & CMP API](file:///c:/Users/zakau/NewsIQ/docs/api/consent.md)**: Cookie preferences, region checks, and logs.

### 3. [Database Reference](file:///c:/Users/zakau/NewsIQ/docs/database/overview.md)
Data structures and query specifications:
- **[Database Schemas](file:///c:/Users/zakau/NewsIQ/docs/database/postgres-schema.md)**: PostgreSQL schemas, tables, indexes, and Alembic.
- **[Redis Structures](file:///c:/Users/zakau/NewsIQ/docs/database/redis-structures.md)**: Caches, token blacklists, and Celery beat keys.

### 4. [AI Pipeline & Summarization](file:///c:/Users/zakau/NewsIQ/docs/ai/overview.md)
Detailed walkthroughs of the AI summarization layers:
- **[AI Ingestion & Summaries](file:///c:/Users/zakau/NewsIQ/docs/ai/overview.md)**: Newspaper4k, Qdrant vectors, and summarization prompts.
- **[Timelines & Differences](file:///c:/Users/zakau/NewsIQ/docs/ai/difference-engine.md)**: Timelining heuristics, prompt structures, and token cost optimization.

### 5. [Security & Compliance](file:///c:/Users/zakau/NewsIQ/docs/security/overview.md)
- **[Security Overview](file:///c:/Users/zakau/NewsIQ/docs/security/overview.md)**: CSRF, CORS, work factors, and session security.
- **[Privacy Compliance](file:///c:/Users/zakau/NewsIQ/docs/privacy-compliance.md)**: GDPR, CCPA/CPRA, and DPDPA mappings.
- **[Cookies & CMP Technical](file:///c:/Users/zakau/NewsIQ/docs/cookies-technical.md)**: Technical detail on browser cookies.

### 6. [Architecture Decisions (ADRs)](file:///c:/Users/zakau/NewsIQ/docs/decisions/README.md)
The history of design decision trade-offs:
- **[ADR-001: Single Backend Architecture](file:///c:/Users/zakau/NewsIQ/docs/decisions/ADR-001-single-backend.md)**
- **[ADR-002: AI Synthesis Pipeline](file:///c:/Users/zakau/NewsIQ/docs/decisions/ADR-002-ai-synthesis-pipeline.md)**
- **[ADR-003: Redis Sessions](file:///c:/Users/zakau/NewsIQ/docs/decisions/ADR-003-redis-sessions.md)**
- **[ADR-004: Personalized Feed](file:///c:/Users/zakau/NewsIQ/docs/decisions/ADR-004-personalized-feed.md)**
- **[ADR-005: Subscription System](file:///c:/Users/zakau/NewsIQ/docs/decisions/ADR-005-subscription-system.md)**

### 7. [Operations Runbooks](file:///c:/Users/zakau/NewsIQ/docs/runbooks/README.md)
Troubleshooting guidelines for common outage scenarios:
- **[Database Outage Runbook](file:///c:/Users/zakau/NewsIQ/docs/runbooks/database-outage.md)**
- **[Redis Cache Failure Runbook](file:///c:/Users/zakau/NewsIQ/docs/runbooks/redis-failure.md)**
- **[LLM API Timeout Runbook](file:///c:/Users/zakau/NewsIQ/docs/runbooks/llm-provider-outage.md)**
- **[Emergency Rollbacks](file:///c:/Users/zakau/NewsIQ/docs/runbooks/emergency-procedures.md)**

### 8. [System Changelogs](file:///c:/Users/zakau/NewsIQ/docs/changelogs/CHANGELOG.md)
- **[Release Log](file:///c:/Users/zakau/NewsIQ/docs/changelogs/CHANGELOG.md)**: Tracking features and schema migrations.

---

## 📋 Owner Registry & Maintenance

Documentation is treated as code. If you make a state-changing change to an API endpoint or database schema:
1. Run the drift checking utility:
   ```bash
   python docs/scripts/drift-check.py
   ```
2. Correct any detected mismatches prior to creating a pull request.
