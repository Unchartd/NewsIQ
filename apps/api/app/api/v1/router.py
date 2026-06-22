"""API v1 router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, consent, oauth, sources, stories, users
from app.core.config import settings

api_router = APIRouter()

role_norm = settings.BACKEND_SERVICE_ROLE.lower().strip()

# Auth endpoints (loaded on both backends to support login/session management)
if role_norm in ("monolith", "user", "processing", "admin"):
    api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# User-facing routes
if role_norm in ("monolith", "user"):

    # Google OAuth endpoints
    api_router.include_router(oauth.router, prefix="/auth", tags=["oauth"])

    # Consent endpoints (CMP)
    api_router.include_router(consent.router, prefix="/consent", tags=["consent"])

    # User endpoints
    api_router.include_router(users.router, prefix="/users", tags=["users"])

    # Source endpoints (read-only for user backend)
    api_router.include_router(sources.router, prefix="/sources", tags=["sources"])

    # Story endpoints (includes /search, /categories, /trending-widgets, /bookmarks)
    api_router.include_router(stories.router, prefix="/stories", tags=["stories"])

# Admin & Observability routes
if role_norm in ("monolith", "processing", "admin"):
    # Admin endpoints (role management, stats, content moderation, replay, tracing)
    api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


@api_router.get("/ping", tags=["system"])
async def ping():
    """Simple ping endpoint to verify API v1 is reachable."""
    return {"message": "pong", "api_version": "v1"}

