"""Infrastructure layer — cloud-agnostic service providers.

This package provides dependency-injection-ready providers for:
  - database/    → DatabaseProvider (wraps SQLAlchemy session factory)
  - cache/       → CacheProvider (wraps Redis)
  - storage/     → StorageProvider (R2, S3, MinIO, local filesystem)
  - observability/ → ObservabilityProvider (Langfuse, OpenTelemetry)

Business logic should import from app.infrastructure.* rather than
accessing external services directly. This ensures that swapping providers
(e.g., Neon → self-hosted PostgreSQL, Upstash → local Redis) requires only
environment variable changes.
"""
