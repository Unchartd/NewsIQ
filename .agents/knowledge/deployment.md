# deployment.md — Deployment and Infrastructure Reference

This reference details the infrastructure layout, environments, and service distributions for NewsIQ.

## 1. Container Environments
Services are containerized using Docker. The standard deployment includes:
- `api`: The FastAPI web server.
- `web`: The React client application, compiled and served.
- `worker`: The Celery or Arq worker container processing background tasks.
- `redis`: Shared message broker and cache.
- `postgres`: Relational data store.
- `mongodb`: Document payload store.
- `qdrant`: Vector indexing store.

## 2. Ingress & Routing
- Inbound traffic on port 80/443 is captured by a reverse proxy (e.g. Nginx or Caddy).
- Static frontend assets are served directly, while paths matching `/api/` are forwarded to the `api` FastAPI container.
