"""Service layer for administrative debugger and observability operations."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.models import (
    Article,
    CanonicalEntity,
    Story,
    StoryArticle,
    StoryContradiction,
    StoryEntity,
)
from app.models.observability_models import (
    CostRecordModel,
    HumanReviewModel,
    LLMTraceModel,
    PipelineRunModel,
    PromptVersionModel,
    StageRunModel,
)
from app.schemas.admin_schemas import (
    AdminLLMTraceSchema,
    AdminStageRunSchema,
    AdminStoryArticleSchema,
    AdminStoryEntitySchema,
    AdminStoryEventSchema,
    ClusterArticleSchema,
    ClusterDebuggerItemSchema,
    ClusterDebuggerResponse,
    CostAnalyticsResponse,
    CostSummaryItemSchema,
    EntityDebuggerItemSchema,
    EntityDebuggerResponse,
    HumanReviewItemSchema,
    HumanReviewQueueResponse,
    MetricsSummaryResponse,
    PipelineStageStatusSchema,
    PipelineStatusResponse,
    PromptComparisonResponse,
    PromptVersionSchema,
    StoryInspectorResponse,
    TimelineDebuggerResponse,
    TimelineEventDebuggerSchema,
)

logger = logging.getLogger(__name__)


class AdminService:
    """Handles business logic for the admin debugging dashboard."""

    async def get_story_inspector_data(
        self, story_id: uuid.UUID, db: AsyncSession
    ) -> StoryInspectorResponse:
        """Fetch all details, articles, events, entities, and logs for a story."""
        # 1. Fetch story and nested relationships
        story_result = await db.execute(
            select(Story)
            .where(Story.id == story_id)
            .options(
                selectinload(Story.articles).selectinload(StoryArticle.article).selectinload(Article.source),
                selectinload(Story.timeline_events),
                selectinload(Story.entities).selectinload(StoryEntity.canonical_entity),
            )
        )
        story = story_result.scalar_one_or_none()
        if not story:
            raise ValueError(f"Story with ID {story_id} not found")

        # 2. Map articles
        articles = []
        for sa in story.articles:
            art = sa.article
            src = art.source
            articles.append(
                AdminStoryArticleSchema(
                    id=art.id,
                    title=art.title or "Untitled",
                    url=art.url,
                    published_at=art.published_at or art.created_at or _now(),
                    source_name=src.name,
                    country_code=src.country_code or "US",
                )
            )

        # 3. Map events
        events = []
        # Since events are extracted at the article level and populated on the story:
        # Let's map the story timeline events as the events schema for simplicity,
        # or fetch events from article_events if available.
        # Let's populate TimelineEvents in both slots if needed, or map timeline events.
        for te in story.timeline_events:
            events.append(
                AdminStoryEventSchema(
                    id=te.id,
                    event_type="Timeline Event",
                    description=te.description or "",
                    actor="Multiple",
                    location=story.location_country or "Unknown",
                )
            )

        # 4. Map entities
        entities = []
        for se in story.entities:
            entities.append(
                AdminStoryEntitySchema(
                    id=se.id,
                    name=se.entity_value,
                    type=se.entity_type,
                    confidence=0.9,  # Default fallback
                    wikidata_id=se.canonical_entity.wikidata_id if se.canonical_entity else None,
                )
            )

        # 5. Fetch LLM traces associated with the story
        trace_result = await db.execute(
            select(LLMTraceModel)
            .where(LLMTraceModel.story_id == story_id)
            .order_by(LLMTraceModel.created_at.desc())
        )
        traces = trace_result.scalars().all()
        llm_traces = [
            AdminLLMTraceSchema(
                id=t.id,
                model=t.model,
                stage=t.stage,
                latency_ms=t.latency_ms,
                cost_usd=t.cost_usd,
                status=t.status,
                created_at=t.created_at,
            )
            for t in traces
        ]

        # 6. Fetch Stage runs associated with the story
        stages_result = await db.execute(
            select(StageRunModel)
            .where(StageRunModel.story_id == story_id)
            .order_by(StageRunModel.started_at.desc())
        )
        stage_runs_list = stages_result.scalars().all()
        stage_runs = [
            AdminStageRunSchema(
                id=sr.id,
                stage=sr.stage,
                status=sr.status,
                started_at=sr.started_at,
                completed_at=sr.completed_at,
                latency_ms=sr.latency_ms,
                retry_count=sr.retry_count,
                error=sr.error,
            )
            for sr in stage_runs_list
        ]

        # 7. Aggregate total cost
        total_cost = sum(t.cost_usd for t in traces)

        return StoryInspectorResponse(
            id=story.id,
            headline=story.headline or "No Headline",
            short_summary=story.short_summary or "No Summary",
            created_at=story.created_at,
            articles=articles,
            events=events,
            entities=entities,
            llm_traces=llm_traces,
            stage_runs=stage_runs,
            total_cost_usd=total_cost,
        )

    async def get_pipeline_status(self, db: AsyncSession) -> PipelineStatusResponse:
        """Fetch status of the most recent pipeline run and its stage runs."""
        # 1. Fetch latest run
        latest_run_result = await db.execute(
            select(PipelineRunModel).order_by(PipelineRunModel.started_at.desc()).limit(1)
        )
        run = latest_run_result.scalar_one_or_none()
        if not run:
            return PipelineStatusResponse(status="idle", stages=[])

        # 2. Fetch all stage runs for this pipeline run
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

    async def get_prompt_versions(
        self, stage: str | None, db: AsyncSession
    ) -> PromptComparisonResponse:
        """Fetch all prompt template versions, optionally filtered by stage."""
        query = select(PromptVersionModel)
        if stage:
            query = query.where(PromptVersionModel.stage == stage)
        query = query.order_by(PromptVersionModel.stage.asc(), PromptVersionModel.version.desc())

        result = await db.execute(query)
        prompts = result.scalars().all()

        return PromptComparisonResponse(
            prompts=[
                PromptVersionSchema(
                    id=p.id,
                    prompt_hash=p.prompt_hash,
                    stage=p.stage,
                    system_prompt=p.system_prompt,
                    user_prompt_template=p.user_prompt_template,
                    version=p.version,
                    is_active=p.is_active,
                    created_at=p.created_at,
                )
                for p in prompts
            ]
        )

    async def get_cost_analytics(self, db: AsyncSession) -> CostAnalyticsResponse:
        """Aggregate total token cost metrics by provider/model/stage."""
        # Query cost records
        result = await db.execute(
            select(
                CostRecordModel.provider,
                CostRecordModel.model,
                CostRecordModel.stage,
                func.sum(CostRecordModel.input_tokens).label("input_tokens"),
                func.sum(CostRecordModel.output_tokens).label("output_tokens"),
                func.sum(CostRecordModel.cost_usd).label("cost_usd"),
            )
            .group_by(CostRecordModel.provider, CostRecordModel.model, CostRecordModel.stage)
            .order_by(func.sum(CostRecordModel.cost_usd).desc())
        )
        rows = result.all()

        breakdown = []
        total_cost = 0.0
        for row in rows:
            cost = float(row.cost_usd or 0.0)
            total_cost += cost
            breakdown.append(
                CostSummaryItemSchema(
                    provider=row.provider,
                    model=row.model,
                    stage=row.stage,
                    input_tokens=int(row.input_tokens or 0),
                    output_tokens=int(row.output_tokens or 0),
                    cost_usd=cost,
                )
            )

        return CostAnalyticsResponse(
            total_cost_usd=round(total_cost, 6),
            breakdown=breakdown,
        )

    async def get_entity_debugger_data(self, db: AsyncSession) -> EntityDebuggerResponse:
        """Fetch confidence metrics and occurrence counts for entity debugging."""
        # Find entities with occurrence count
        result = await db.execute(
            select(
                StoryEntity.entity_value,
                StoryEntity.entity_type,
                func.count(StoryEntity.id).label("occurrences"),
            )
            .group_by(StoryEntity.entity_value, StoryEntity.entity_type)
            .order_by(func.count(StoryEntity.id).desc())
            .limit(100)
        )
        rows = result.all()

        entities = []
        for row in rows:
            # Look up a canonical entity matching this value
            ce_result = await db.execute(
                select(CanonicalEntity).where(CanonicalEntity.name == row.entity_value).limit(1)
            )
            ce = ce_result.scalar_one_or_none()
            entities.append(
                EntityDebuggerItemSchema(
                    id=ce.id if ce else uuid.uuid4(),
                    name=row.entity_value,
                    type=row.entity_type,
                    confidence=0.95 if ce else 0.70,
                    wikidata_id=ce.wikidata_id if ce else None,
                    occurrences=int(row.occurrences or 0),
                )
            )

        return EntityDebuggerResponse(entities=entities)

    async def get_cluster_debugger_data(self, db: AsyncSession) -> ClusterDebuggerResponse:
        """Fetch article group sizes and grouping details for active clusters."""
        # Query stories with articles
        result = await db.execute(
            select(Story)
            .options(
                selectinload(Story.articles).selectinload(StoryArticle.article).selectinload(Article.source)
            )
            .order_by(Story.created_at.desc())
            .limit(20)
        )
        stories = result.scalars().all()

        clusters = []
        for s in stories:
            articles = [
                ClusterArticleSchema(
                    id=sa.article.id,
                    title=sa.article.title or "Untitled",
                    source_name=sa.article.source.name,
                    published_at=sa.article.published_at or sa.article.created_at or _now(),
                )
                for sa in s.articles
            ]
            clusters.append(
                ClusterDebuggerItemSchema(
                    story_id=s.id,
                    headline=s.headline or "No Headline",
                    article_count=len(s.articles),
                    avg_similarity=0.88,  # Hardcoded placeholder
                    articles=articles,
                )
            )

        return ClusterDebuggerResponse(clusters=clusters)

    async def get_timeline_debugger_data(
        self, story_id: uuid.UUID, db: AsyncSession
    ) -> TimelineDebuggerResponse:
        """Fetch timeline events and contradictions for a story."""
        # Fetch story
        story_result = await db.execute(
            select(Story).where(Story.id == story_id).options(selectinload(Story.timeline_events))
        )
        story = story_result.scalar_one_or_none()
        if not story:
            raise ValueError(f"Story {story_id} not found")

        # Fetch contradictions
        contra_result = await db.execute(
            select(StoryContradiction).where(StoryContradiction.story_id == story_id)
        )
        contras = contra_result.scalars().all()

        timeline = [
            TimelineEventDebuggerSchema(
                id=te.id,
                event_date=te.event_time.isoformat() if te.event_time else (te.event_time_raw or ""),
                description=te.description or "",
                articles_referenced=[],
            )
            for te in story.timeline_events
        ]

        return TimelineDebuggerResponse(
            story_id=story_id,
            timeline=timeline,
            contradictions=[c.description for c in contras],
        )

    async def get_human_review_queue(self, db: AsyncSession) -> HumanReviewQueueResponse:
        """Fetch active queue of human reviewer feedback events."""
        result = await db.execute(
            select(HumanReviewModel).order_by(HumanReviewModel.created_at.desc()).limit(100)
        )
        reviews = result.scalars().all()

        return HumanReviewQueueResponse(
            reviews=[
                HumanReviewItemSchema(
                    id=r.id,
                    story_id=r.story_id,
                    action=r.action,
                    target_type=r.target_type,
                    before_value=r.before_value,
                    after_value=r.after_value,
                    notes=r.notes,
                    created_at=r.created_at,
                )
                for r in reviews
            ]
        )

    async def apply_review_action(
        self,
        story_id: uuid.UUID,
        action: str,
        target_type: str | None,
        target_id: uuid.UUID | None,
        before_value: dict[str, Any] | None,
        after_value: dict[str, Any] | None,
        notes: str | None,
        db: AsyncSession,
    ) -> None:
        """Log a human action correction and apply changes to database."""
        # 1. Log review action
        review = HumanReviewModel(
            story_id=story_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_value=before_value,
            after_value=after_value,
            notes=notes,
        )
        db.add(review)

        # 2. Implement the DB updates based on action
        if action == "approve":
            result = await db.execute(select(Story).where(Story.id == story_id))
            story = result.scalar_one_or_none()
            if story:
                story.story_status = "approved"

        elif action == "reject":
            result = await db.execute(select(Story).where(Story.id == story_id))
            story = result.scalar_one_or_none()
            if story:
                story.story_status = "rejected"

        elif action == "correct_summary" and after_value:
            result = await db.execute(select(Story).where(Story.id == story_id))
            story = result.scalar_one_or_none()
            if story:
                if "headline" in after_value:
                    story.headline = after_value["headline"]
                if "short_summary" in after_value:
                    story.short_summary = after_value["short_summary"]
                if "detailed_summary" in after_value:
                    story.detailed_summary = after_value["detailed_summary"]

        await db.commit()

    async def get_metrics_summary(self, db: AsyncSession) -> MetricsSummaryResponse:
        """Calculate overall cost, tokens, runs, and current queue sizes."""
        # Count pipeline runs
        runs_count = (await db.execute(select(func.count(PipelineRunModel.id)))).scalar_one() or 0
        failed_count = (
            await db.execute(
                select(func.count(PipelineRunModel.id)).where(PipelineRunModel.status == "failed")
            )
        ).scalar_one() or 0

        # Aggregate cost from CostRecordModel
        total_cost = (await db.execute(select(func.sum(CostRecordModel.cost_usd)))).scalar_one() or 0.0
        total_tokens = (
            await db.execute(
                select(func.sum(CostRecordModel.input_tokens + CostRecordModel.output_tokens))
            )
        ).scalar_one() or 0

        # Query Redis for queue sizes
        import redis.asyncio as aioredis
        try:
            r = aioredis.from_url(settings.CELERY_BROKER_URL)
            waiting = await r.llen("celery")
            await r.aclose()
        except Exception:
            waiting = 0

        return MetricsSummaryResponse(
            total_pipeline_runs=runs_count,
            failed_runs_count=failed_count,
            total_llm_cost=round(float(total_cost), 4),
            total_tokens_consumed=int(total_tokens),
            waiting_jobs_count=waiting,
            active_jobs_count=0,  # Fallback since workers query requires control plane
        )


def _now() -> datetime:
    from datetime import UTC
    return datetime.now(UTC).replace(tzinfo=None)


admin_service = AdminService()
