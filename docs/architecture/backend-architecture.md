# Backend Architecture Reference

This document describes the design patterns, dependency injection system, and service/repository boundaries within the NewsIQ FastAPI backend application.

---

## 1. Directory Structure

The backend application is located under `apps/api/app/`.

```text
apps/api/app/
├── api/                  # REST API Router Endpoints
│   └── v1/               # Version 1 API Prefix Routers (auth, consent, stories...)
├── core/                 # Core System Configuration & Middleware
│   ├── config.py         # Pydantic Settings (env parsing)
│   ├── database.py       # SQLAlchemy Session Engine Configuration
│   ├── deps.py           # Dependency Injection Functions (auth, db sessions)
│   ├── rate_limiter.py   # Redis IP-based Rate Limiting Middleware
│   └── security.py       # JWT Cryptography and Password hashing utilities
├── models/               # SQLAlchemy ORM Models Discovery
│   ├── models.py         # Main Entity Tables (User, Story, Article...)
│   └── consent.py        # CMP Schemas (ConsentPreference, ConsentAuditLog)
├── repositories/         # Database Query Access Objects (SQL query bounds)
│   └── user_repository.py
├── schemas/              # Pydantic Serialization / Input Validation models
│   ├── auth.py           # Requests/Responses validation models
│   └── consent.py        # CMP request validations
├── services/             # Core Business Logic Services
│   ├── auth_service.py   # Registration, logins, password resets
│   └── session_service.ts# Redis and DB Session cache management
├── tasks/                # Celery Background Ingest Task Pipelines
└── workers/              # Celery Queue Configurations & Lifespan
```

---

## 2. Dependency Injection Layer (`core/deps.py`)

FastAPI's dependency injection system coordinates access control and resource allocation. Core injections include:

- **`get_db`**: Generator yielding an asynchronous SQLAlchemy `AsyncSession` per HTTP request, ensuring automatic transaction rollbacks on failures and resource cleanups.
- **`get_current_user`**: Validates the access token in Bearer headers or cookies, retrieves the user entity, and returns it. Returns `None` for anonymous visitors.
- **`require_user`**: Reuses `get_current_user` but raises a `401 Unauthorized` exception if the token is missing or invalid.
- **`require_premium`** / **`require_admin`**: Gates operations by verifying `user.role` after validating authentication.

---

## 3. Service-Repository Pattern
To isolate business logic from database serialization details:
- **Repositories**: Standardize querying structures (e.g. `UserRepository.get_by_email`). Repositories deal strictly with SQL model executions.
- **Services**: Coordinate operations, execute business constraints, write cache updates, and trigger background workers. For example, `AuthService.login` verifies password work-factors, updates failure lockout counts, registers login timestamps, writes the session into Redis via `SessionService`, and returns token pairs.

---

## 4. Background Workers & Task Queues (Celery)
For long-running AI pipelines and ingestion operations:
- **Task Broker**: Redis stores the task queue lists.
- **Beat Scheduler**: A cron-like Celery Beat process regularly dispatches tasks (e.g., polling RSS feeds every hour).
- **Execution Queues**:
  - `ingestion`: Parses articles and inserts them into PostgreSQL.
  - `clustering`: Generates embeddings, triggers Qdrant similarity match, and groups articles into stories.
  - `summarization`: Contacts the LLM APIs (Gemini/OpenAI) to draft timelines and difference metrics.
- All background tasks execute inside separate worker nodes, leaving the main FastAPI REST threads responsive.

---

## 5. Async Safety & Pipeline Boundaries

When working in asynchronous database sessions (`AsyncSession`), accessing un-loaded SQLAlchemy ORM relationships triggers synchronous database queries under the hood. In async contexts, this raises `sqlalchemy.exc.MissingGreenlet` exceptions, which abort transactions and silent-fail operations.

To prevent this in the Story Synthesis pipeline:

> [!IMPORTANT]
> **Engineering Safety Rule: ORM-Safe Pipeline Boundaries**
> 1. Pipeline C stages, compilers, agents, publishers, and validators must **never** execute implicit database queries or traverse lazy-loaded ORM relationships.
> 2. All required data must be eagerly loaded (e.g. using `selectinload` or explicit queries) or mapped into immutable Data Transfer Objects (DTOs) before entering the pipeline.
> 3. Downstream services must operate strictly on pure Python dataclasses (`ArticleContext`, `EventContext`, `EntityContext`, `SourceContext`, `StoryContext`) defined in [synthesis_context.py](file:///apps/api/app/schemas/synthesis_context.py).

---

## 6. Extraction Pipeline & Typed Contracts

NewsIQ uses a multi-provider extraction pipeline to retrieve full article content. This layer is decoupled and hardened using strongly typed contracts:

- **Unified Contracts (`app/services/extraction/types.py`)**: All extraction providers (`LocalCrawlerProvider`, `TavilyExtractProvider`, `FirecrawlProvider`) must return a unified, structured `ExtractionResult` dataclass wrapping `ExtractionFailure` (an enum of possible errors) and `ExtractionDiagnostics` telemetry.
- **Local Crawler Isolation**: All local parsing (using `newspaper4k`, `trafilatura`, `readability-lxml`, and custom BS4 cleaners) resides within `LocalCrawlerProvider`. `CrawlerService` acts as a thin compatibility shim.
- **Domain Metrics & Policy (`DomainExtractionPolicy`)**: The platform dynamically tracks and persists domain-level success rates and latency telemetry using Exponential Moving Averages (EMA) to guide future intelligent routing strategies.

