# ADR-001: Single Backend Architecture

## Status
Approved

## Context
NewsIQ comprises multiple processing parts: HTTP routes, background RSS/GNews scraping, vector DB upsert, and LLM synthesis. Initially, these could have been split into separate microservices (e.g., auth service, ingestion service, synthesis service) using lightweight message brokers.

## Decision
We consolidate the core API gateway and all background tasks into a single FastAPI backend codebase (`apps/api`).
- **Orchestration**: Celery workers load the same codebase, importing services directly.
- **Task Dispatch**: Celery Beat schedules and dispatches background tasks through Redis queues to Celery workers.
- **Relational Access**: All processes use a unified SQLAlchemy repository layer pointing to a single PostgreSQL database.

## Alternatives Considered
1. **Microservices (Independent Codebases)**: Increased operational overhead, duplicate Pydantic models, complex integration testing, and distributed transaction complexity.
2. **Next.js Serverless Functions**: Difficult to support long-running, CPU-bound background scraping and HDBSCAN clustering processes without hitting execution timeouts.

## Trade-offs
- **Pros**:
  - **Shared Schemas**: Pydantic models and SQLAlchemy entities are defined once, eliminating serialization drifts.
  - **Operational Simplicity**: One service to deploy, test, and run locally via Docker.
  - **Transactional Integrity**: Avoids distributed transaction issues; database cascades can be handled natively.
- **Cons**:
  - **Deployment Scaling**: Scaling requires replicating the entire codebase container, though workers can be scaled independently of the API gateway.
  - **Shared Resources**: The API and Celery workers share database connections, meaning connection pool starvation must be managed.

## Consequences
- The API gateway and Celery worker share the same Dockerfile.
- Scalability is achieved by scaling Celery worker instances independently in `docker-compose.yml` or K8s.
