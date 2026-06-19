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
