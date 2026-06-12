"""API v1 router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import auth, oauth, users, sources

api_router = APIRouter()

# Auth endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Google OAuth endpoints
api_router.include_router(oauth.router, prefix="/auth", tags=["oauth"])

# User endpoints
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Source endpoints
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])


@api_router.get("/ping", tags=["system"])
async def ping():
    """Simple ping endpoint to verify API v1 is reachable."""
    return {"message": "pong", "api_version": "v1"}
