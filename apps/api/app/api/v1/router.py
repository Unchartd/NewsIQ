"""API v1 router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, oauth, sources, stories, users

api_router = APIRouter()

# Auth endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Google OAuth endpoints
api_router.include_router(oauth.router, prefix="/auth", tags=["oauth"])

# User endpoints
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Source endpoints
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])

# Story endpoints (includes /search, /categories, /trending-widgets, /bookmarks)
api_router.include_router(stories.router, prefix="/stories", tags=["stories"])

# Admin endpoints (role management, stats, content moderation)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


@api_router.get("/ping", tags=["system"])
async def ping():
    """Simple ping endpoint to verify API v1 is reachable."""
    return {"message": "pong", "api_version": "v1"}
