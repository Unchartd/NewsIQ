"""FastAPI application entry point."""

import logging
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import request_id_ctx_var, setup_logging
from app.core.rate_limiter import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.exceptions.auth import AuthException

# Initialize structured logging
setup_logging(settings.DEBUG)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # ── Startup ───────────────────────────────────────────────────────────────
    import os
    import shutil

    # Initialize Prometheus multiprocess directory
    prom_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if prom_dir:
        try:
            if os.path.exists(prom_dir):
                for f in os.listdir(prom_dir):
                    fp = os.path.join(prom_dir, f)
                    if os.path.isfile(fp):
                        os.unlink(fp)
                    elif os.path.isdir(fp):
                        shutil.rmtree(fp)
            else:
                os.makedirs(prom_dir, exist_ok=True)
            logger.info("Prometheus multiprocess metrics directory initialized: %s", prom_dir)
        except Exception as e:
            logger.warning("Failed to clean/create PROMETHEUS_MULTIPROC_DIR: %s", e)

    # Run full startup validation (checks secrets, DB, Redis, etc.)
    try:
        from app.core.startup import run_startup_validation

        await run_startup_validation()
    except RuntimeError as e:
        # Re-raise to prevent the app from accepting traffic
        logger.critical("Startup validation failed — refusing to start: %s", e)
        raise

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("NewsIQ API shutting down.")

    # Flush pending Langfuse traces before exit
    try:
        from app.infrastructure.observability import observability_provider

        await observability_provider.flush()
        logger.info("Langfuse traces flushed.")
    except Exception as e:
        logger.warning("Failed to flush Langfuse on shutdown: %s", e)

    # Close shared HTTP Client Pool
    try:
        from app.core.http_client import http_client_pool

        await http_client_pool.close()
    except Exception as e:
        logger.warning("Failed to close shared HTTP client pool on shutdown: %s", e)

    # Close Vector DB Service Clients
    try:
        from app.services.vector_service import vector_service

        await vector_service.close()
    except Exception as e:
        logger.warning("Failed to close VectorService on shutdown: %s", e)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI News Intelligence Platform — understand any story in 30 seconds.",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# ── Sentry ────────────────────────────────────────────────────────────────────
if settings.SENTRY_DSN:
    from app.core.sentry_integration import before_send_handler, before_send_transaction_handler

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        before_send=before_send_handler,
        before_send_transaction=before_send_transaction_handler,
    )

# ── Middleware (applied in reverse order — last added is outermost) ───────────

# Rate limiting
app.add_middleware(RateLimitMiddleware, limit=100, window=60)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS — register last so it wraps all other middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique request ID to every request and response."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_ctx_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    request_id_ctx_var.reset(token)
    return response


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    """Basic CSRF protection — validates Origin/Referer on state-changing methods."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        if origin or referer:
            client_origin = origin or (
                referer.split("/", 3)[0] + "//" + referer.split("/", 3)[2] if referer else None
            )
            if client_origin and client_origin not in settings.CORS_ORIGINS:
                return __import__("fastapi").responses.JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF check failed: invalid Origin or Referer"},
                )
    return await call_next(request)


# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(AuthException)
async def auth_exception_handler(request: Request, exc: AuthException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global catch-all for unhandled exceptions."""
    logger.exception("Unhandled exception occurred: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

# Health check router (mounted at root level, not under /api/v1)
from app.api.v1.health import router as health_router  # noqa: E402

app.include_router(health_router)

# API v1 routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ── Metrics endpoint ──────────────────────────────────────────────────────────


@app.get("/metrics", tags=["monitoring"])
def metrics():
    """Prometheus metrics endpoint."""
    import os

    from fastapi import Response
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        generate_latest,
        multiprocess,
    )

    import app.core.metrics  # noqa: F401

    prom_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if prom_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        data = generate_latest(registry)
    else:
        data = generate_latest()

    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
