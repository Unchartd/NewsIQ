"""Pydantic schemas for the admin observability and debugger API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AdminStoryArticleSchema(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    published_at: datetime
    source_name: str
    country_code: str


class AdminStoryEventSchema(BaseModel):
    id: uuid.UUID
    event_type: str
    description: str
    actor: str
    location: str


class AdminStoryEntitySchema(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    confidence: float
    wikidata_id: str | None = None


class AdminLLMTraceSchema(BaseModel):
    id: uuid.UUID
    model: str
    stage: str
    latency_ms: float
    cost_usd: float
    status: str
    created_at: datetime


class AdminStageRunSchema(BaseModel):
    id: uuid.UUID
    stage: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: float
    retry_count: int
    error: str | None = None


class StoryInspectorResponse(BaseModel):
    id: uuid.UUID
    headline: str
    short_summary: str
    created_at: datetime
    articles: list[AdminStoryArticleSchema]
    events: list[AdminStoryEventSchema]
    entities: list[AdminStoryEntitySchema]
    llm_traces: list[AdminLLMTraceSchema]
    stage_runs: list[AdminStageRunSchema]
    total_cost_usd: float
    story_status: str = "active"

    model_config = ConfigDict(from_attributes=True)


class PipelineStageStatusSchema(BaseModel):
    stage: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latency_ms: float
    error: str | None = None


class PipelineStatusResponse(BaseModel):
    run_id: uuid.UUID | None = None
    status: str
    stages: list[PipelineStageStatusSchema]


class PromptVersionSchema(BaseModel):
    id: uuid.UUID
    prompt_hash: str
    stage: str
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    version: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptComparisonResponse(BaseModel):
    prompts: list[PromptVersionSchema]


class CostSummaryItemSchema(BaseModel):
    provider: str
    model: str
    stage: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostAnalyticsResponse(BaseModel):
    total_cost_usd: float
    breakdown: list[CostSummaryItemSchema]


class EntityDebuggerItemSchema(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    confidence: float
    wikidata_id: str | None = None
    occurrences: int


class EntityDebuggerResponse(BaseModel):
    entities: list[EntityDebuggerItemSchema]


class ClusterArticleSchema(BaseModel):
    id: uuid.UUID
    title: str
    source_name: str
    published_at: datetime


class ClusterDebuggerItemSchema(BaseModel):
    story_id: uuid.UUID
    headline: str
    article_count: int
    avg_similarity: float
    articles: list[ClusterArticleSchema]


class ClusterDebuggerResponse(BaseModel):
    clusters: list[ClusterDebuggerItemSchema]


class TimelineEventDebuggerSchema(BaseModel):
    id: uuid.UUID
    event_date: str
    description: str
    articles_referenced: list[uuid.UUID]


class TimelineDebuggerResponse(BaseModel):
    story_id: uuid.UUID
    timeline: list[TimelineEventDebuggerSchema]
    contradictions: list[str]


class HumanReviewItemSchema(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    action: str
    target_type: str | None = None
    before_value: dict[str, Any] | None = None
    after_value: dict[str, Any] | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HumanReviewQueueResponse(BaseModel):
    reviews: list[HumanReviewItemSchema]


class MetricsSummaryResponse(BaseModel):
    total_pipeline_runs: int
    failed_runs_count: int
    total_llm_cost: float
    total_tokens_consumed: int
    waiting_jobs_count: int
    active_jobs_count: int
