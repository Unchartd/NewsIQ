# NewsIQ Documentation Audit & Risk Assessment

This document provides a comprehensive audit of all existing documentation files in the NewsIQ repository, identifies coverage gaps, and assesses security/operational risks associated with undocumented systems.

---

## 1. Existing Documentation Files

### A. Root Level Documents
- **[README.md](file:///c:/Users/zakau/NewsIQ/README.md)**: Baseline local setup guide. (Up-to-date for development run instructions).
- **[Product Requirements Document.md](file:///c:/Users/zakau/NewsIQ/Product%20Requirements%20Document.md)**: Original product specs. (Static product historical context).
- **[Technical Requirements Document.md](file:///c:/Users/zakau/NewsIQ/Technical%20Requirements%20Document.md)**: Original technical specifications. (Static tech context).
- **[Backend Schema Document.md](file:///c:/Users/zakau/NewsIQ/Backend%20Schema%20Document.md)**: Historical schema outline. (**Outdated**: Missing Alembic migration steps, `consent_preferences`, `consent_audit_logs`, and Redis schemas).
- **[newsiq_system_architecture.md](file:///c:/Users/zakau/NewsIQ/newsiq_system_architecture.md)**: Mermaid charts for pipeline ingestion and clusters. (Accurate, but lacks CMP, auth-gating, and frontend routing context).
- **[data_pipeline_flowcharts.md](file:///c:/Users/zakau/NewsIQ/data_pipeline_flowcharts.md)**: Flow diagrams of rss feed processing and timeline generation. (Accurate).
- **[UX Design Brief.md](file:///c:/Users/zakau/NewsIQ/UX%20Design%20Brief.md)** & **[UX Flow Document.md](file:///c:/Users/zakau/NewsIQ/UX%20Flow%20Document.md)**: Initial layout briefs. (Historical visual design notes).
- **[Step-by-Step Implementation Plan.md](file:///c:/Users/zakau/NewsIQ/Step-by-Step%20Implementation%20Plan.md)**: Old plan checklist. (Safe to archive).

### B. `/docs` Subdirectory Documents
- **[security-review.md](file:///c:/Users/zakau/NewsIQ/docs/security-review.md)**: Audit of network, cookie flags, and token rotations. (Up-to-date).
- **[cookies-technical.md](file:///c:/Users/zakau/NewsIQ/docs/cookies-technical.md)**: Technical detail on CMP schemas, API routes, and IP hashes. (Up-to-date).
- **[cookie-inventory.md](file:///c:/Users/zakau/NewsIQ/docs/cookie-inventory.md)**: Tabular cookie mapping by regulatory defaults. (Up-to-date).
- **[cookie-architecture.md](file:///c:/Users/zakau/NewsIQ/docs/cookie-architecture.md)**: CMP sequence flow diagrams. (Up-to-date).
- **[consent-flow.md](file:///c:/Users/zakau/NewsIQ/docs/consent-flow.md)**: React consent toggling UX mapping. (Up-to-date).
- **[privacy-compliance.md](file:///c:/Users/zakau/NewsIQ/docs/privacy-compliance.md)**: GDPR/CCPA compliance mapping. (Up-to-date).
- **[legal-audit.md](file:///c:/Users/zakau/NewsIQ/docs/legal-audit.md)**: Legal context for compliance framework. (Historical).
- **[legal-implementation-checklist.md](file:///c:/Users/zakau/NewsIQ/docs/legal-implementation-checklist.md)**: Completed roadmap checklist. (Complete).

---

## 2. Identified Coverage Gaps

### A. Missing Documents (Undocumented Systems)
1. **Frontend Architecture Reference**: Next.js App Router folders, authentication redirect guards, layout states, and global ZustStores.
2. **Backend Architecture Reference**: Dependency injection layers (`deps.py`), database session lifecycle, services/repositories interfaces.
3. **API reference Docs**: Full REST request/response schemas, error code definitions, pagination limits, and headers.
4. **AI Pipeline & Summarization**: In-depth description of Celery tasks, Newspaper4k extraction, Qdrant vector models, Difference Engine prompt patterns, timeline synthesis, and token cost mitigation.
5. **Database Schemas**: SQL Constraints, indices, Alembic migration paths, and server-side Redis hash shapes.
6. **Infrastructure & Runbooks**: Docker container orchestration, Celery-worker queues, observability guides, and outage runbooks (DB failure, Redis crash, LLM timeouts).
7. **Architectural Decision Records (ADRs)**: Formal history of core architectural decisions.

### B. Outdated Documents
- **[Backend Schema Document.md](file:///c:/Users/zakau/NewsIQ/Backend%20Schema%20Document.md)**: Lacks new tables and lacks descriptions of relational models (e.g. bookmarks, cluster, sources, consent, session caches).

### C. Conflicting / Redundant Documents
- **[Step-by-Step Implementation Plan.md](file:///c:/Users/zakau/NewsIQ/Step-by-Step%20Implementation%20Plan.md)**: Overlaps with historical checklists and requirements. Should be marked as legacy.

---

## 3. Technical Risk Assessment

We classify documentation gaps by technical risk to prioritize drafting schedules.

| Gaps | Component | Risk level | Impact |
| :--- | :--- | :---: | :--- |
| **AI Ingestion & Summarization** | `Celery` / `Qdrant` / `LLM` | **Critical** | Failures in prompts, timeouts, or embeddings lack mitigation logs. High cloud provider costs if cache layers misbehave. |
| **API Reference Endpoints** | `FastAPI` / `/api/v1/*` | **High** | Developers lack clear API contracts, slowing frontend integrations and increasing bugs. |
| **Database schemas & Migration** | `PostgreSQL` / `Alembic` | **High** | Poor visibility into database locks, schema indexes, or the exact Alembic upgrade workflows. |
| **Security & Audits** | `JWT` / `CSRF` | **Medium** | Incident response and secret key rotation flows are undocumented. |
| **Infrastructure Deployment** | `Docker` / `Redis` | **Medium** | Deployment configurations and worker container management depend on tacit knowledge. |

---

## 4. Remediation Priority Plan
1. **High Priority**: Database schemas, API reference details, AI summarization pipeline.
2. **Medium Priority**: Architecture visual overviews, deployment setups, ADRs.
3. **Operational Priority**: Incident response runbooks, drift detection script.
