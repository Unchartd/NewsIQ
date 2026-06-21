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
from app.models.models import Article, Source, Story, User, CanonicalEntity, StoryArticle
from app.models.observability_models import PipelineRunModel, StageRunModel, LLMTraceModel
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
    run_id: uuid.UUID | None = None,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get status of the latest or specified pipeline execution run (admin only)."""
    if run_id:
        from app.schemas.admin_schemas import PipelineStageStatusSchema
        run_result = await db.execute(
            select(PipelineRunModel).where(PipelineRunModel.id == run_id)
        )
        run = run_result.scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")

        stages_result = await db.execute(
            select(StageRunModel)
            .where(StageRunModel.run_id == run.id)
            .order_by(StageRunModel.started_at.asc())
        )
        stage_runs = stages_result.scalars().all()

        stages = [
            PipelineStageStatusSchema(
                stage=sr.stage,
                status=sr.status,
                started_at=sr.started_at,
                completed_at=sr.completed_at,
                latency_ms=sr.latency_ms,
                error=sr.error,
            )
            for sr in stage_runs
        ]

        return PipelineStatusResponse(
            run_id=run.id,
            status=run.status,
            stages=stages,
        )
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
    stage_norm = stage.lower().strip()
    mapping = {
        "nlp_analysis": "entity_extraction",
        "entity_extraction": "entity_extraction",
        "contradiction": "contradiction_detection",
        "contradiction_engine": "contradiction_detection",
        "contradiction_detection": "contradiction_detection",
        "timeline": "timeline_generation",
        "timeline_builder": "timeline_generation",
        "timeline_generation": "timeline_generation",
        "summarization": "summary_generation",
        "ai_summarization": "summary_generation",
        "summary_generation": "summary_generation",
    }
    stage_resolved = mapping.get(stage_norm, stage_norm)

    if stage_resolved not in {"entity_extraction", "contradiction_detection", "timeline_generation", "summary_generation"}:
        raise HTTPException(
            status_code=400,
            detail=f"Stage '{stage}' is not replayable. Replayable stages: NLP Analysis, Contradiction Engine, Timeline Builder, AI Summarization."
        )

    from app.workers.tasks import replay_story_stage_task
    replay_story_stage_task.delay(str(story_id), stage_resolved)
    return MessageResponse(message=f"Replay of stage {stage_resolved} triggered for story {story_id}.")


@router.get("/pipeline/runs")
async def list_pipeline_runs(
    limit: int = 50,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List historical pipeline executions (admin only)."""
    stmt = select(PipelineRunModel).order_by(PipelineRunModel.started_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    runs = res.scalars().all()
    return [
        {
            "id": str(r.id),
            "trace_id": str(r.trace_id),
            "trigger": r.trigger,
            "pipeline_type": r.pipeline_type,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "total_latency_ms": r.total_latency_ms,
            "error": r.error,
        }
        for r in runs
    ]


@router.get("/pipeline/runs/{run_id}/stages/{stage}")
async def get_stage_run_details(
    run_id: uuid.UUID,
    stage: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details (inputs, outputs, metrics, errors) of a specific stage run (admin only)."""
    stage_lower = stage.lower().strip()
    stmt = select(StageRunModel).where(
        StageRunModel.run_id == run_id,
        StageRunModel.stage == stage_lower
    )
    res = await db.execute(stmt)
    stage_run = res.scalar_one_or_none()
    if not stage_run:
        raise HTTPException(status_code=404, detail=f"Stage run not found for stage {stage}")

    llm_stmt = select(LLMTraceModel).where(
        LLMTraceModel.run_id == run_id,
        LLMTraceModel.stage == stage_lower
    )
    llm_res = await db.execute(llm_stmt)
    llm_traces = llm_res.scalars().all()

    traces_payload = [
        {
            "id": str(t.id),
            "provider": t.provider,
            "model": t.model,
            "system_prompt": t.system_prompt,
            "user_prompt": t.user_prompt,
            "response_text": t.response_text,
            "input_tokens": t.input_tokens,
            "output_tokens": t.output_tokens,
            "total_tokens": t.total_tokens,
            "latency_ms": t.latency_ms,
            "cost_usd": t.cost_usd,
            "status": t.status,
            "error": t.error,
        }
        for t in llm_traces
    ]

    return {
        "id": str(stage_run.id),
        "run_id": str(stage_run.run_id),
        "trace_id": str(stage_run.trace_id),
        "stage": stage_run.stage,
        "status": stage_run.status,
        "started_at": stage_run.started_at.isoformat() if stage_run.started_at else None,
        "completed_at": stage_run.completed_at.isoformat() if stage_run.completed_at else None,
        "latency_ms": stage_run.latency_ms,
        "retry_count": stage_run.retry_count,
        "error": stage_run.error,
        "error_type": stage_run.error_type,
        "story_id": str(stage_run.story_id) if stage_run.story_id else None,
        "article_id": str(stage_run.article_id) if stage_run.article_id else None,
        "metadata": stage_run.metadata_payload or {},
        "llm_traces": traces_payload,
    }


@router.get("/pipeline/runs/{run_id}/stages/{stage}/logs")
async def get_stage_run_logs(
    run_id: uuid.UUID,
    stage: str,
    _admin: User = Depends(require_admin),
):
    """Retrieve all cached logs for a stage run (admin only)."""
    import redis
    from app.core.config import settings
    stage_lower = stage.lower().strip()
    r = redis.from_url(settings.REDIS_URL)
    redis_key = f"newsiq:logs:{run_id}:{stage_lower}"
    logs = r.lrange(redis_key, 0, -1)
    return [line.decode("utf-8") if isinstance(line, bytes) else line for line in logs]


@router.get("/pipeline/runs/{run_id}/stages/{stage}/logs/stream")
async def stream_stage_run_logs(
    run_id: uuid.UUID,
    stage: str,
):
    """Stream logs live via SSE for a specific stage run."""
    import redis.asyncio as aioredis
    from app.core.config import settings
    stage_lower = stage.lower().strip()

    async def log_generator():
        r = aioredis.from_url(settings.REDIS_URL)
        # Yield existing logs first
        redis_key = f"newsiq:logs:{run_id}:{stage_lower}"
        existing_logs = await r.lrange(redis_key, 0, -1)
        for line in existing_logs:
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            yield f"data: {decoded}\n\n"

        pubsub = r.pubsub()
        redis_channel = f"newsiq:logs:{run_id}:{stage_lower}:stream"
        await pubsub.subscribe(redis_channel)
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    decoded = message['data'].decode('utf-8') if isinstance(message['data'], bytes) else message['data']
                    yield f"data: {decoded}\n\n"
        finally:
            await pubsub.unsubscribe(redis_channel)
            await r.aclose()

    return StreamingResponse(log_generator(), media_type="text/event-stream")


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


class EntityOverrideRequest(BaseModel):
    wikidata_id: str | None = Field(None, max_length=50)


class ClusterMergeRequest(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID


@router.patch("/entities/{entity_id}", response_model=MessageResponse)
async def update_entity_wikidata(
    entity_id: uuid.UUID,
    body: EntityOverrideRequest,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Override the Wikidata ID for a canonical entity (admin only)."""
    result = await db.execute(select(CanonicalEntity).where(CanonicalEntity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        from app.models.models import StoryEntity
        result_se = await db.execute(select(StoryEntity).order_by(StoryEntity.id.desc()))
        story_entities = result_se.scalars().all()
        matching_se = None
        for se in story_entities:
            if uuid.uuid5(uuid.NAMESPACE_DNS, se.entity_value) == entity_id:
                matching_se = se
                break
        if matching_se:
            entity = CanonicalEntity(
                canonical_name=matching_se.entity_value,
                entity_type=matching_se.entity_type,
                wikidata_id=body.wikidata_id,
                aliases=[matching_se.entity_value],
                metadata_payload={"description": "Created on patch override"},
            )
            db.add(entity)
            await db.commit()
        else:
            raise HTTPException(status_code=404, detail="Entity not found")
    else:
        entity.wikidata_id = body.wikidata_id
        await db.commit()
    
    try:
        from app.services.cache_service import cache_service
        import re
        slug = re.sub(r"[^a-z0-9]+", "_", entity.canonical_name.lower())
        await cache_service.delete(f"newsiq:entity_link:{slug}")
    except Exception:
        pass
        
    return MessageResponse(message="Entity Wikidata ID updated successfully.")


@router.post("/clusters/merge", response_model=MessageResponse)
async def merge_clusters(
    body: ClusterMergeRequest,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Merge source cluster into target cluster (admin only)."""
    source_result = await db.execute(select(Story).where(Story.id == body.source_id))
    source_story = source_result.scalar_one_or_none()
    target_result = await db.execute(select(Story).where(Story.id == body.target_id))
    target_story = target_result.scalar_one_or_none()
    
    if not source_story or not target_story:
        raise HTTPException(status_code=404, detail="One or both stories not found")
        
    stmt = select(StoryArticle).where(StoryArticle.story_id == body.source_id)
    res = await db.execute(stmt)
    sa_links = res.scalars().all()
    
    for link in sa_links:
        exist_stmt = select(StoryArticle).where(
            StoryArticle.story_id == body.target_id,
            StoryArticle.article_id == link.article_id
        )
        exist_res = await db.execute(exist_stmt)
        if not exist_res.scalar_one_or_none():
            link.story_id = body.target_id
        else:
            await db.delete(link)
            
    await db.flush()
    
    await admin_service.apply_review_action(
        story_id=body.target_id,
        action="merge",
        target_type="story",
        target_id=body.source_id,
        before_value={"source_story_id": str(body.source_id)},
        after_value={"merged_into_target_id": str(body.target_id)},
        notes=f"Merged cluster {body.source_id} into {body.target_id}",
        db=db,
    )
    
    await db.delete(source_story)
    await db.commit()
    
    from app.services.clustering_service import clustering_service
    stmt_art = select(Article).join(StoryArticle).where(StoryArticle.story_id == body.target_id)
    res_art = await db.execute(stmt_art)
    all_articles = list(res_art.scalars().all())
    
    await clustering_service.generate_story_content(target_story, all_articles, db)
    await clustering_service.compute_trending_score(target_story, db)
    
    return MessageResponse(message="Story clusters merged successfully.")


@router.post("/clusters/{story_id}/split", response_model=MessageResponse)
async def split_cluster(
    story_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Split a story cluster into sub-clusters based on event similarity (admin only)."""
    result = await db.execute(select(Story).where(Story.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
        
    stmt = select(Article).join(StoryArticle).where(StoryArticle.story_id == story_id)
    res = await db.execute(stmt)
    all_articles = list(res.scalars().all())
    
    if len(all_articles) <= 1:
        raise HTTPException(status_code=400, detail="Cannot split a cluster with 1 or fewer articles")
        
    from app.services.clustering_service import clustering_service
    from app.models.models import ArticleEvent
    
    sub_clusters = []
    for art in all_articles:
        matched_sub = None
        stmt_evt = select(ArticleEvent).where(ArticleEvent.article_id == art.id).limit(1)
        res_evt = await db.execute(stmt_evt)
        art_evt = res_evt.scalar_one_or_none()
        
        if art_evt:
            for sub in sub_clusters:
                total_sim = 0.0
                for sub_art in sub:
                    stmt_sub = select(ArticleEvent).where(ArticleEvent.article_id == sub_art.id).limit(1)
                    res_sub = await db.execute(stmt_sub)
                    sub_evt = res_sub.scalar_one_or_none()
                    if sub_evt:
                        total_sim += clustering_service._compute_event_similarity_direct(art_evt, sub_evt)
                    else:
                        total_sim += 0.0
                avg_sim = total_sim / len(sub)
                if avg_sim >= 0.80:
                    matched_sub = sub
                    break
        if matched_sub is not None:
            matched_sub.append(art)
        else:
            sub_clusters.append([art])
            
    if len(sub_clusters) <= 1:
        sub_clusters = [[all_articles[0]], all_articles[1:]]
        
    await admin_service.apply_review_action(
        story_id=story_id,
        action="split",
        target_type="story",
        target_id=story_id,
        before_value={"article_count": len(all_articles)},
        after_value={"sub_clusters_count": len(sub_clusters)},
        notes=f"Split cluster {story_id} into {len(sub_clusters)} clusters",
        db=db,
    )
    
    await db.delete(story)
    await db.commit()
    
    from app.models.models import StoryMetric
    
    for art_list in sub_clusters:
        new_story_id = uuid.uuid4()
        now = datetime.now(UTC).replace(tzinfo=None)
        new_story = Story(
            id=new_story_id,
            story_status="active",
            first_seen_at=min((a.published_at for a in art_list if a.published_at), default=now),
            trend_score=1.0,
            created_at=now,
            updated_at=now,
        )
        db.add(new_story)
        
        for art in art_list:
            link = StoryArticle(story_id=new_story_id, article_id=art.id)
            db.add(link)
            
        metrics = StoryMetric(story_id=new_story_id, views=0, bookmarks=0, shares=0, clicks=0)
        db.add(metrics)
        await db.commit()
        
        try:
            await clustering_service.generate_story_content(new_story, art_list, db)
            await clustering_service.compute_trending_score(new_story, db)
        except Exception:
            pass
            
    return MessageResponse(message=f"Story cluster split into {len(sub_clusters)} clusters successfully.")
