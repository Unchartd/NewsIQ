"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import uuid

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.logging import setup_logging, request_id_ctx_var

# Initialize structured logging
setup_logging(settings.DEBUG)

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

    # Initialize Meilisearch index on startup
    try:
        from app.services.search_service import search_service
        await search_service.init_index()
        logger.info("Meilisearch index initialized.")
    except Exception as e:
        logger.warning("Could not initialize Meilisearch index at startup: %s", e)

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

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
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

# Request ID middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_ctx_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    request_id_ctx_var.reset(token)
    return response

# CSRF middleware
@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    # Only check state-changing methods
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        
        # If both are missing, it might be a server-to-server or non-browser client.
        # Strict CSRF would block it, but for our API we'll allow it if neither is present.
        # If either is present, it must match allowed origins.
        if origin or referer:
            client_origin = origin or (referer.split("/", 3)[0] + "//" + referer.split("/", 3)[2] if referer else None)
            if client_origin and client_origin not in settings.CORS_ORIGINS:
                # Reject request
                return __import__("fastapi").responses.JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF check failed: invalid Origin or Referer"},
                )
    return await call_next(request)

# Exception handlers
from app.exceptions.auth import AuthException
from fastapi.responses import JSONResponse

@app.exception_handler(AuthException)
async def auth_exception_handler(request: Request, exc: AuthException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

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
        from app.core.database import async_session_factory
        from sqlalchemy import text

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
