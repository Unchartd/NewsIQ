---
trigger: always_on
---

# backend.md — Backend Coding Rules for NewsIQ

These rules govern the development, extension, and maintenance of server-side application layers.

## 1. FastAPI & Routes
- **Endpoint Layout**: Structure routes logically under domain-specific routers.
- **Dependency Isolation**: Enforce dependency injection patterns for sharing database pools, client instances, and user context.
- **Asynchronous Execution**: Utilize async handlers for non-blocking I/O operations (e.g. database transactions, external API requests).

## 2. Background Tasks & Workers
- **Idempotency**: Ensure all background worker executions are idempotent and safe for repeated runs.
- **Queue Segregation**: Segment tasks by priority (e.g., separating interactive updates from long-running ingestion workflows).
