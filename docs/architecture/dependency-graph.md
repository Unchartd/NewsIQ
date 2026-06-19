# Dependency Graph & Boundaries

This document maps package boundaries, project layers, and internal dependency graphs for NewsIQ.

---

## 1. Project Folder Hierarchy

NewsIQ is organized as a monorepo workspace:

```text
/
├── apps/
│   ├── api/            # Python FastAPI backend service
│   │   ├── app/        # Main API codebase
│   │   └── tests/      # API tests (pytest)
│   └── web/            # Next.js SPA frontend web application
│       ├── src/        # Next.js sources (components, stores, lib)
│       └── public/     # Static assets (images, logos)
├── docs/               # Central Documentation Hub (Index: /docs/README.md)
└── docker-compose.yml  # Local multi-container development orchestration
```

---

## 2. Backend Module Dependency Graph

Within the `api` app, the imports graph runs strictly top-down to prevent circular import locks:

```
                  +---------------------------+
                  |    uvicorn (Entrypoint)   |
                  +-------------+-------------+
                                |
                                v
                  +---------------------------+
                  |       app/main.py         |
                  +-------------+-------------+
                                |
                                v
                  +---------------------------+
                  |     app/api/v1/router     |
                  +-------------+-------------+
                                |
                                v
                  +---------------------------+
                  |    app/api/v1/endpoints   |
                  | (auth, consent, stories)  |
                  +-------+-------------+-----+
                          |             |
            +-------------+             +-------------+
            v                                         v
+---------------------------+             +---------------------------+
|     app/services/         |             |      app/core/deps        |
|  (auth, session, vector)  |             | (authentication, get_db)  |
+-----------+---------------+             +-------------+-------------+
            |                                           |
            +---------------------+                     |
                                  v                     v
                        +---------------------------+
                        |    app/repositories/      |
                        |      (user_repo)          |
                        +-------------+-------------+
                                      |
                                      v
                        +---------------------------+
                        |      app/models/          |
                        |  (SQLAlchemy Schemas)     |
                        +-------------+-------------+
                                      |
                                      v
                        +---------------------------+
                        |    app/core/database      |
                        |     (Base, Session)       |
                        +---------------------------+
```

### Boundary Constraints:
- **Models**: Must not import repositories or services (independent leaf nodes).
- **Repositories**: Can import models, but must not import services.
- **Services**: Can import repositories and models; coordinate operations across multiple repositories.
- **Routers / Endpoints**: Can import dependencies (`deps.py`) and services; must not execute direct raw SQL statements (delegate to services or repositories).

---

## 3. Frontend Store & Library Dependencies

```
          +--------------------------------------------+
          |         Next.js UI Pages (app/)            |
          +-------+--------------+--------------+------+
                  |              |              |
                  v              v              v
          +---------------+  +-------+  +--------------+
          |   Components  |  | Stores|  |  apiClient   |
          |  (CMP Banner) |  | (Auth)|  | (token-store)|
          +---------------+  +-------+  +--------------+
```

- **Stores**: Maintain state; do not directly access browser API elements or window triggers (handled inside page lifecycle hooks).
- **apiClient**: Centralized Axios client; holds token refreshes; all components import this rather than standard `fetch` or raw `axios` instances.
- **CMP Provider**: Mounts at layout level; acts as a guard blocking tracking scripts from accessing DOM contexts.
