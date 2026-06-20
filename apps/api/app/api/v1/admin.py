"""Admin-only API endpoints for user and content management."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.models import Article, Source, Story, User
from app.schemas.admin_schemas import (
    ClusterDebuggerResponse,
    CostAnalyticsResponse,
    EntityDebuggerResponse,
    HumanReviewQueueResponse,
    MetricsSummaryResponse,
    PipelineStatusResponse,
    PromptComparisonResponse,
    StoryInspectorResponse,
    TimelineDebuggerResponse,
)
from app.schemas.auth import MessageResponse, UserResponse
from app.services.admin_service import admin_service

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

    # Remove from search index and caches
    try:
        from app.services.cache_service import cache_service
        from app.services.search_service import search_service

        await search_service.delete_story(str(story_id))
        await cache_service.invalidate_story(str(story_id))
    except Exception:
        pass

    return MessageResponse(message="Story deleted.")


# ──────────────────────────────────────────────
# Observability & Debugger Endpoints (Admin Only)
# ──────────────────────────────────────────────


@router.get("/stories/{story_id}", response_model=StoryInspectorResponse)
async def inspect_story(
    story_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get full details, articles, events, entities, and logs for a story (admin only)."""
    try:
        return await admin_service.get_story_inspector_data(story_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def pipeline_status(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get status of the latest pipeline execution run (admin only)."""
    return await admin_service.get_pipeline_status(db)


@router.get("/prompts", response_model=PromptComparisonResponse)
async def list_prompts(
    stage: str | None = None,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all versioned prompt templates (admin only)."""
    return await admin_service.get_prompt_versions(stage, db)


@router.get("/costs", response_model=CostAnalyticsResponse)
async def cost_analytics(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated token cost and usage analytics (admin only)."""
    return await admin_service.get_cost_analytics(db)


@router.get("/entities", response_model=EntityDebuggerResponse)
async def entity_debugger(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get confidence metrics and occurrence counts for entity debugging (admin only)."""
    return await admin_service.get_entity_debugger_data(db)


@router.get("/clusters", response_model=ClusterDebuggerResponse)
async def cluster_debugger(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get article grouping details for active clusters (admin only)."""
    return await admin_service.get_cluster_debugger_data(db)


@router.get("/timeline/{story_id}", response_model=TimelineDebuggerResponse)
async def timeline_debugger(
    story_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get timeline events and contradictions for a story (admin only)."""
    try:
        return await admin_service.get_timeline_debugger_data(story_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/review/queue", response_model=HumanReviewQueueResponse)
async def human_review_queue(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get queue of human reviewer feedback events (admin only)."""
    return await admin_service.get_human_review_queue(db)


class ReviewActionPayload(BaseModel):
    action: str = Field(..., description="approve, reject, merge, split, correct_entity, mark_hallucination, correct_summary")
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    before_value: dict[str, Any] | None = None
    after_value: dict[str, Any] | None = None
    notes: str | None = None


@router.post("/review/{story_id}/action", response_model=MessageResponse)
async def submit_review_action(
    story_id: uuid.UUID,
    body: ReviewActionPayload,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Submit human review correction feedback (admin only)."""
    await admin_service.apply_review_action(
        story_id=story_id,
        action=body.action,
        target_type=body.target_type,
        target_id=body.target_id,
        before_value=body.before_value,
        after_value=body.after_value,
        notes=body.notes,
        db=db,
    )
    return MessageResponse(message="Review action applied successfully.")


@router.post("/replay/{story_id}", response_model=MessageResponse)
async def replay_story(
    story_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a replay of the full pipeline for a story (admin only)."""
    from app.workers.tasks import replay_story_task
    replay_story_task.delay(str(story_id))
    return MessageResponse(message=f"Replay triggered for story {story_id}.")


@router.post("/replay/{story_id}/{stage}", response_model=MessageResponse)
async def replay_story_stage(
    story_id: uuid.UUID,
    stage: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a replay of a specific stage for a story (admin only)."""
    from app.workers.tasks import replay_story_stage_task
    replay_story_stage_task.delay(str(story_id), stage)
    return MessageResponse(message=f"Replay of stage {stage} triggered for story {story_id}.")



@router.get("/pipeline/stream")
async def stream_pipeline_status():
    """SSE endpoint streaming real-time pipeline status transitions."""

    import redis.asyncio as aioredis

    from app.core.config import settings

    async def event_generator():
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe("newsiq-pipeline-events")
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    yield f"data: {message['data'].decode('utf-8') if isinstance(message['data'], bytes) else message['data']}\n\n"
        finally:
            await pubsub.unsubscribe("newsiq-pipeline-events")
            await r.aclose()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
async def metrics_summary(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get overall cost, tokens, runs, and current queue sizes (admin only)."""
    return await admin_service.get_metrics_summary(db)
