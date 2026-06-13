"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

_INSECURE_DEFAULT_KEY = "change-me-in-production-use-openssl-rand-hex-32"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # ——— Startup ———
    # Guard: reject the default SECRET_KEY in production
    if not settings.DEBUG and settings.SECRET_KEY == _INSECURE_DEFAULT_KEY:
        raise RuntimeError(
            "SECRET_KEY is set to the insecure default value. "
            "Generate a secure key with: openssl rand -hex 32"
        )

    if settings.DEBUG and settings.SECRET_KEY == _INSECURE_DEFAULT_KEY:
        logger.warning(
            "WARNING: Using the default SECRET_KEY. "
            "This is only acceptable in local development. "
            "Set a real SECRET_KEY before deploying to production."
        )

    # Initialize Qdrant collection on startup
    try:
        from app.services.vector_service import vector_service
        await vector_service.init_collection()
        logger.info("Qdrant collection initialized.")
    except Exception as e:
        logger.warning("Could not initialize Qdrant collection at startup: %s", e)

    yield
    # ——— Shutdown ———
    logger.info("NewsIQ API shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI News Intelligence Platform — understand any story in 30 seconds.",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimitMiddleware, limit=100, window=60)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["monitoring"])
async def health_check():
    """Basic liveness probe."""
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/ready", tags=["monitoring"])
async def readiness_check():
    """Readiness probe — verifies DB and Redis connectivity."""
    checks: dict[str, str] = {}

    # PostgreSQL check
    try:
        from sqlalchemy import text
        from app.core.database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Redis check
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
