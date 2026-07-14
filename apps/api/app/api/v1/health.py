"""Comprehensive health check endpoints for all infrastructure services.

Endpoints:
  GET /health                → Liveness probe (always fast, no I/O)
  GET /health/database       → PostgreSQL connectivity + latency
  GET /health/cache          → Redis PING + latency
  GET /health/storage        → Storage backend reachability
  GET /health/llm            → LLM provider key presence
  GET /health/search         → Meilisearch connectivity
  GET /health/observability  → Langfuse connectivity
  GET /ready                 → Combined readiness probe (DB + Redis required)

All individual endpoints return:
  {
    "status": "ok" | "degraded" | "error" | "disabled",
    "latency_ms": float,
    "service": str,
    ...
  }
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter(tags=["health"])

# Application start time (for uptime calculation)
_START_TIME = time.monotonic()


@router.get("/health")
async def liveness():
    """Liveness probe — always returns 200 if the process is alive.

    No I/O performed. Suitable for Kubernetes/Coolify liveness probes.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "role": settings.BACKEND_SERVICE_ROLE,
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/database")
async def health_database():
    """Check PostgreSQL / Neon database connectivity."""
    from app.infrastructure.database import database_provider

    result = await database_provider.health_check()
    code = 200 if result["status"] == "ok" else 503
    return JSONResponse(
        status_code=code,
        content={
            "service": "database",
            "provider": "neon" if "neon.tech" in settings.DATABASE_URL else "postgresql",
            **result,
        },
    )


@router.get("/health/cache")
async def health_cache():
    """Check Redis / Upstash cache connectivity."""
    from app.infrastructure.cache import cache_provider

    result = await cache_provider.health_check()
    code = 200 if result["status"] == "ok" else 503
    tls = settings.redis_uses_tls
    return JSONResponse(
        status_code=code,
        content={
            "service": "cache",
            "provider": "upstash" if tls else "redis",
            "tls": tls,
            **result,
        },
    )


@router.get("/health/storage")
async def health_storage():
    """Check storage backend (R2 / S3 / MinIO / local) connectivity."""
    from app.infrastructure.storage import get_storage_provider

    t0 = time.monotonic()
    try:
        provider = get_storage_provider()
        result = await provider.health_check()
        latency = round((time.monotonic() - t0) * 1000, 2)
        result["latency_ms"] = latency
        code = 200 if result["status"] == "ok" else 503
    except Exception as e:
        latency = round((time.monotonic() - t0) * 1000, 2)
        result = {"status": "error", "error": str(e), "latency_ms": latency}
        code = 503
    return JSONResponse(
        status_code=code,
        content={"service": "storage", **result},
    )


@router.get("/health/llm")
async def health_llm():
    """Check LLM provider API key presence (no live API call to avoid costs)."""
    providers = {
        "gemini": bool(settings.GEMINI_API_KEY or settings.GEMINI_API_KEY_EMBEDDING),
        "openai": bool(settings.OPENAI_API_KEY),
        "groq": bool(settings.GROQ_API_KEY),
        "cerebras": bool(settings.CEREBRAS_API_KEY),
        "nvidia": bool(settings.NVIDIA_API_KEY),
    }
    configured = [k for k, v in providers.items() if v]
    status = "ok" if configured else "degraded"
    return JSONResponse(
        status_code=200 if configured else 200,  # LLM is never a 503 — app works without it
        content={
            "service": "llm",
            "status": status,
            "configured_providers": configured,
            "providers": providers,
            "embedding_model": settings.EMBEDDING_MODEL,
            "summarization_model": settings.SUMMARIZATION_MODEL,
        },
    )


@router.get("/health/search")
async def health_search():
    """Check Meilisearch connectivity."""
    t0 = time.monotonic()
    try:
        from app.services.search_service import search_service

        if not search_service.enabled:
            return JSONResponse(
                status_code=200,
                content={
                    "service": "search",
                    "status": "disabled",
                    "latency_ms": 0,
                },
            )
        # Use the internal Meilisearch client health endpoint
        await search_service.init_index()
        latency_ms = (time.monotonic() - t0) * 1000
        return JSONResponse(
            status_code=200,
            content={
                "service": "search",
                "status": "ok",
                "latency_ms": round(latency_ms, 2),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "service": "search",
                "status": "error",
                "error": str(e),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            },
        )


@router.get("/health/observability")
async def health_observability():
    """Check Langfuse observability provider status."""
    from app.infrastructure.observability import observability_provider

    result = await observability_provider.health_check()
    code = 200  # Observability is never a hard dependency
    return JSONResponse(
        status_code=code,
        content={"service": "observability", **result},
    )


@router.get("/health/qdrant")
async def health_qdrant():
    """Check Qdrant vector database connectivity."""
    t0 = time.monotonic()
    try:
        from app.services.vector_service import vector_service

        collections = await vector_service.client.get_collections()
        latency_ms = (time.monotonic() - t0) * 1000
        return JSONResponse(
            status_code=200,
            content={
                "service": "qdrant",
                "status": "ok",
                "latency_ms": round(latency_ms, 2),
                "collections_count": len(collections.collections),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "service": "qdrant",
                "status": "error",
                "error": str(e),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            },
        )


@router.get("/ready")
async def readiness():
    """Readiness probe — verifies all critical services (DB + Redis) are reachable.

    Returns 200 only when the application is ready to serve traffic.
    Returns 503 if any critical service is unavailable.
    """
    checks: dict[str, dict] = {}

    # Database (critical)
    from app.infrastructure.database import database_provider

    checks["database"] = await database_provider.health_check()

    # Redis (critical)
    from app.infrastructure.cache import cache_provider

    checks["cache"] = await cache_provider.health_check()

    all_critical_ok = all(v.get("status") == "ok" for v in checks.values())
    overall = "ready" if all_critical_ok else "not_ready"

    return JSONResponse(
        status_code=200 if all_critical_ok else 503,
        content={
            "status": overall,
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
