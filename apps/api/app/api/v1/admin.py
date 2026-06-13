"""Admin-only API endpoints for user and content management."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.models import Article, Source, Story, User
from app.schemas.auth import MessageResponse, UserResponse

router = APIRouter()

VALID_ROLES = {"guest", "user", "premium", "admin"}
VALID_PLANS = {"free", "pro", "enterprise"}


class RoleUpdateRequest(BaseModel):
    """Admin payload to change a user's role and/or subscription plan."""

    role: str | None = Field(None, description="One of: guest, user, premium, admin")
    subscription_plan: str | None = Field(None, description="One of: free, pro, enterprise")


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    limit: int = 50,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    users = result.scalars().all()
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            name=u.name,
            image_url=u.image_url,
            role=u.role,
            subscription_plan=u.subscription_plan,
            status=u.status,
            created_at=u.created_at.isoformat() if u.created_at else "",
        )
        for u in users
    ]


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: RoleUpdateRequest,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Change a user's role and/or subscription plan (admin only).

    This is the ONLY supported path for privilege changes. The user-facing
    profile endpoint intentionally cannot modify role or plan.
    """
    if body.role is not None and body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {VALID_ROLES}.")
    if body.subscription_plan is not None and body.subscription_plan not in VALID_PLANS:
        raise HTTPException(
            status_code=400, detail=f"Invalid plan. Must be one of {VALID_PLANS}."
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if body.role is not None:
        user.role = body.role
    if body.subscription_plan is not None:
        user.subscription_plan = body.subscription_plan
    user.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        image_url=user.image_url,
        role=user.role,
        subscription_plan=user.subscription_plan,
        status=user.status,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.get("/stats")
async def get_admin_stats(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return high-level platform statistics (admin only)."""
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    story_count = (await db.execute(select(func.count()).select_from(Story))).scalar_one()
    article_count = (await db.execute(select(func.count()).select_from(Article))).scalar_one()
    source_count = (await db.execute(select(func.count()).select_from(Source))).scalar_one()

    return {
        "users": user_count,
        "stories": story_count,
        "articles": article_count,
        "sources": source_count,
    }


@router.delete("/stories/{story_id}", response_model=MessageResponse)
async def delete_story(
    story_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a story and its cascaded sub-records (admin only)."""
    result = await db.execute(select(Story).where(Story.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found.")
    await db.delete(story)
    await db.commit()
    return MessageResponse(message="Story deleted.")
