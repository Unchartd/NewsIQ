# NewsIQ Documentation Inventory & Dependency Matrix

This document maps ownership, maintenance statuses, completeness coverage, and system dependencies for all technical documentation.

---

## 1. Documentation Inventory Registry

| Document Name | Owner | Purpose | Last Updated | Status | Coverage | System Dependencies |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **System Overview** | DevOps / Arch | High-level topology and component architecture. | June 19, 2026 | New | High | All services (Docker, DB, Cache) |
| **Frontend Architecture** | Frontend | Details App Router, stores, and CMP. | June 19, 2026 | New | High | Next.js, Axios, Zustand |
| **Backend Architecture** | Backend | Details FastAPI, repositories, and dependencies. | June 19, 2026 | New | High | Uvicorn, SQLAlchemy |
| **Event & Data Flows** | Backend / AI | Diagrams of crawling pipelines and clustering. | June 19, 2026 | New | High | Celery, Redis, Qdrant |
| **Dependency Graph** | DevOps | Import directories and module constraints. | June 19, 2026 | New | Medium | Python import structures |
| **API Reference Suite** | Backend | Endpoint, schema, and error contracts. | June 19, 2026 | New | High | FastAPI, Pydantic |
| **Database Schemas** | Backend / DBA | PostgreSQL tables, indexes, and migrations. | June 19, 2026 | New | High | Alembic, PostgreSQL |
| **Redis Structures** | Backend | Key structures, TTL policies, and queue states. | June 19, 2026 | New | High | Redis, Celery Beat |
| **AI Ingestion & Clusters** | AI Team | Ingestion, embedding, and vector schemas. | June 19, 2026 | New | High | Newspaper4k, Qdrant, OpenAI |
| **Difference Engine** | AI Team | Prompt architectures and difference timeline heuristics. | June 19, 2026 | New | High | LangChain, LLM APIs |
| **Security Architecture** | Security | JWT, cookie flags, CORS, and CSRF protection. | June 19, 2026 | Updated | High | Starlette Security Headers |
| **Privacy & CMP Specs** | Privacy | GDPR/CCPA matrices, cookie flags, and IP hashes. | June 19, 2026 | Updated | High | CMP Provider, backend consent API |
| **ADR Suite (001-005)** | Arch / Tech Leads | Log of structural architecture decision records. | June 19, 2026 | New | High | System architecture |
| **Operations Runbooks** | DevOps | Troubleshooting and recovery procedures. | June 19, 2026 | New | High | DB, Redis, LLM endpoints |
| **System Changelogs** | Tech Leads | Log of changes and Alembic migrations. | June 19, 2026 | New | Medium | Alembic history |
| **Drift Detection Suite** | Tooling | Tool configuration and drift warnings report. | June 19, 2026 | New | High | Python parsing script |
| **SEO Audit** | SEO Eng | Technical SEO, AEO, GEO, LLMO, and E-E-A-T audit. | June 20, 2026 | New | High | Next.js App, crawler configs |
| **AEO & GEO Playbook** | AI & Growth | Citation and answer optimizations for LLM search. | June 20, 2026 | New | High | AI pipelines, summaries, entities |
| **E-E-A-T Strategy** | Growth / Legal | Transparency hubs, publisher policies, and schema signals. | June 20, 2026 | New | High | Public SSR pages, JSON-LD |
| **Technical SEO Guide** | SEO Eng / Dev | Server Wrappers, dynamic sitemaps, and robots.txt. | June 20, 2026 | New | High | robots.ts, sitemap.ts, config |

---

## 2. Maintenance & Audit Protocol

- **Review Cycle**: Quarterly.
- **Auto-Verification**: Documentation drift check script executes during developer checkins.
- **Coverage Levels**:
  - **High**: Matches code line-for-line with actual schema attributes and route definitions.
  - **Medium**: Structural conceptual walkthrough; subject to updates on package shifts.
  - **Low**: Stub file or basic conceptual mapping.
