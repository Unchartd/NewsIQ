"""API v1 router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, consent, oauth, sources, stories, users
from app.core.config import settings

api_router = APIRouter()

role_norm = settings.BACKEND_SERVICE_ROLE.lower().strip()

# Shared endpoints (loaded on both backends to support SRE operations and feeds delivery)
if role_norm in ("monolith", "user", "processing", "admin"):
    api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
    api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
    api_router.include_router(stories.router, prefix="/stories", tags=["stories"])

# User-facing routes
if role_norm in ("monolith", "user"):
    # Google OAuth endpoints
    api_router.include_router(oauth.router, prefix="/auth", tags=["oauth"])

    # Consent endpoints (CMP)
    api_router.include_router(consent.router, prefix="/consent", tags=["consent"])

    # User endpoints
    api_router.include_router(users.router, prefix="/users", tags=["users"])

# Admin & Observability routes
if role_norm in ("monolith", "processing", "admin"):
    # Admin endpoints (role management, stats, content moderation, replay, tracing)
    api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


@api_router.get("/ping", tags=["system"])
async def ping():
    """Simple ping endpoint to verify API v1 is reachable."""
    return {"message": "pong", "api_version": "v1"}
