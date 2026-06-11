"""API v1 router — aggregates all sub-routers."""

from fastapi import APIRouter

api_router = APIRouter()


# Placeholder health route for v1
@api_router.get("/ping", tags=["system"])
async def ping():
    """Simple ping endpoint to verify API v1 is reachable."""
    return {"message": "pong", "api_version": "v1"}


# Sub-routers will be added in subsequent phases:
# from app.api.v1 import auth, stories, search, users, trending, categories, bookmarks, admin
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(stories.router, prefix="/stories", tags=["stories"])
# etc.
