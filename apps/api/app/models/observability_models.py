"""SQLAlchemy ORM models for the NewsIQ Observability Platform.

Tables:
    - pipeline_runs       Top-level pipeline execution records
    - stage_runs          Per-stage execution within a pipeline run
    - llm_traces          Individual LLM API call records
    - token_usage         Aggregated token usage by provider/model/day
    - cost_records        Computed costs per story/article/provider
    - retry_history       Every retry attempt with error details
    - prompt_versions     Versioned prompt templates with hash dedup
    - error_logs          Structured error records with trace correlation
    - queue_metrics       Periodic snapshots of queue health
    - human_reviews       Human feedback and corrections

All tables use UUID v7 primary keys and timezone-naive UTC timestamps,
consistent with the existing NewsIQ models.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    """Return current UTC time (timezone-naive, consistent with DB storage)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _generate_uuid() -> uuid.UUID:
    """Generate a UUID v7 (time-ordered) if available, else v4."""
    try:
        from uuid7 import uuid7

        return uuid7()
    except ImportError:
        return uuid.uuid4()


# ──────────────────────────────────────────────
# Pipeline Execution Tracking
# ──────────────────────────────────────────────


class PipelineRunModel(Base):
    """Top-level record for a single pipeline execution (batch or incremental).

    A PipelineRun encompasses one complete cycle: ingest → embed → extract → cluster → synthesize.
    Each run has a unique trace_id that propagates to all child stages and logs.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, index=True)
    trigger: Mapped[str] = mapped_column(
        String(50), default="manual"
    )  # celery_beat, manual, replay, api
    pipeline_type: Mapped[str] = mapped_column(
        String(50), default="batch"
    )  # batch, incremental, replay
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True
    )
    is_replay: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(
        String(30), default="pending"
    )  # pending, running, success, failed
    started_at: Mapped[datetime] = mapped_column(default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    total_stages: Mapped[int] = mapped_column(Integer, default=0)
    successful_stages: Mapped[int] = mapped_column(Integer, default=0)
    failed_stages: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_pipeline_runs_started", "started_at"),
        Index("idx_pipeline_runs_status", "status"),
    )


class StageRunModel(Base):
    """Execution record for a single pipeline stage within a PipelineRun.

    Each stage (ingestion, embedding, clustering, etc.) gets its own record
    with timing, status, and error information.
    """

    __tablename__ = "stage_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), index=True
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    stage: Mapped[str] = mapped_column(String(100))  # PipelineStage enum value
    status: Mapped[str] = mapped_column(
        String(30), default="pending"
    )  # pending, running, success, failed, skipped
    started_at: Mapped[datetime] = mapped_column(default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    metadata_payload: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_stage_runs_stage", "stage"),
        Index("idx_stage_runs_started", "started_at"),
        Index("idx_stage_runs_run_stage", "run_id", "stage"),
    )


# ──────────────────────────────────────────────
# LLM Observability
# ──────────────────────────────────────────────


class LLMTraceModel(Base):
    """Record of a single LLM API call (Gemini, OpenAI, Anthropic).

    Captures the full lifecycle: prompt → response → tokens → cost → latency.
    Supports replay by storing the exact prompts used.
    """

    __tablename__ = "llm_traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(50))  # gemini, openai, anthropic
    model: Mapped[str] = mapped_column(String(100))
    stage: Mapped[str] = mapped_column(String(100))  # event_extraction, summary, etc.
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="success")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    __table_args__ = (
        Index("idx_llm_traces_provider_model", "provider", "model"),
        Index("idx_llm_traces_stage", "stage"),
    )


class TokenUsageModel(Base):
    """Aggregated daily token usage by provider and model.

    Used for cost forecasting and budget tracking dashboards.
    Aggregated from llm_traces by a periodic task.
    """

    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    date: Mapped[datetime] = mapped_column(index=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    stage: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        Index("idx_token_usage_date_provider", "date", "provider", "model", unique=True),
    )


class CostRecordModel(Base):
    """Cost record per story/article, allowing per-entity cost analysis.

    Computed from llm_traces when a story finishes processing.
    """

    __tablename__ = "cost_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    stage: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    __table_args__ = (
        Index("idx_cost_records_provider", "provider"),
        Index("idx_cost_records_created", "created_at"),
    )


# ──────────────────────────────────────────────
# Error & Retry Tracking
# ──────────────────────────────────────────────


class RetryHistoryModel(Base):
    """Record of every retry attempt for any pipeline operation.

    Tracks the progression of retries with escalating delays and error details.
    """

    __tablename__ = "retry_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    stage: Mapped[str] = mapped_column(String(100))
    attempt_number: Mapped[int] = mapped_column(Integer)
    error_type: Mapped[str] = mapped_column(String(255))
    error_message: Mapped[str] = mapped_column(Text)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    wait_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    story_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    article_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)


class ErrorLogModel(Base):
    """Structured error record with full trace correlation.

    Richer than basic logging — stores categorized errors with trace context
    for the error analytics dashboard.
    """

    __tablename__ = "error_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    stage: Mapped[str] = mapped_column(String(100))
    error_category: Mapped[str] = mapped_column(
        String(50)
    )  # llm_failure, db_failure, api_failure, worker_crash, parse_error
    error_type: Mapped[str] = mapped_column(String(255))
    error_message: Mapped[str] = mapped_column(Text)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="error")  # warning, error, critical
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    __table_args__ = (
        Index("idx_error_logs_category", "error_category"),
        Index("idx_error_logs_severity", "severity"),
    )


class PipelineFailureModel(Base):
    """Structured pipeline failure logs for Sentry-like observability."""

    __tablename__ = "pipeline_failures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    stage: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="failed")
    input_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    exception: Mapped[str] = mapped_column(Text)
    stack_trace: Mapped[str] = mapped_column(Text)
    error_category: Mapped[str] = mapped_column(
        String(50)
    )  # system_error, llm_error, data_error, agent_error
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    latency: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(default=_now, index=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_pipeline_failures_category", "error_category"),
        Index("idx_pipeline_failures_stage", "stage"),
        Index("idx_pipeline_failures_resolved", "resolved"),
    )


# ──────────────────────────────────────────────
# Prompt Management
# ──────────────────────────────────────────────


class PromptVersionModel(Base):
    """Versioned prompt template with content-hash deduplication.

    Stores the full prompt text and computes a SHA-256 hash.
    If the same prompt content is used again, the existing version is reused.
    """

    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    prompt_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True
    )  # SHA-256 of system_prompt + user_prompt_template
    stage: Mapped[str] = mapped_column(String(100))
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    # Prompt Platform v5 Columns
    prompt_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lifecycle_state: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="production"
    )
    parent_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deprecated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (Index("idx_prompt_versions_stage", "stage"),)


# ──────────────────────────────────────────────
# Queue Monitoring
# ──────────────────────────────────────────────


class QueueMetricsModel(Base):
    """Periodic snapshot of Celery queue health.

    Collected by a scheduled task to feed the queue health dashboard.
    """

    __tablename__ = "queue_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    queue_name: Mapped[str] = mapped_column(String(100))
    active_jobs: Mapped[int] = mapped_column(Integer, default=0)
    waiting_jobs: Mapped[int] = mapped_column(Integer, default=0)
    completed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    failed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    dead_letter_jobs: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    worker_count: Mapped[int] = mapped_column(Integer, default=0)
    captured_at: Mapped[datetime] = mapped_column(default=_now, index=True)


# ──────────────────────────────────────────────
# Human Review
# ──────────────────────────────────────────────


class HumanReviewModel(Base):
    """Human reviewer feedback and corrections for AI-generated content.

    Stores actions like approve, reject, split, merge, correct_entity,
    mark_hallucination, correct_summary — along with before/after data.
    """

    __tablename__ = "human_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # FK to users — nullable for system reviews
    action: Mapped[str] = mapped_column(
        String(50)
    )  # approve, reject, split, merge, correct_entity, mark_hallucination, correct_summary
    target_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # entity, summary, cluster, timeline
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # ID of the specific entity/summary being corrected
    before_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    __table_args__ = (
        Index("idx_human_reviews_story", "story_id"),
        Index("idx_human_reviews_action", "action"),
    )


# ──────────────────────────────────────────────
# Function Call Observability
# ──────────────────────────────────────────────


class FunctionRunModel(Base):
    """Execution record for tracked helper functions across workers.

    Captures parameters, results, duration, and error states.
    """

    __tablename__ = "function_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    function_name: Mapped[str] = mapped_column(String(255), index=True)
    caller: Mapped[str] = mapped_column(String(255), default="system")
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    span_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="success")  # success, failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    arguments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)


class PipelineTraceModel(Base):
    """Rich execution trace logging for all pipeline stages (PipelineTrace)."""

    __tablename__ = "pipeline_traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_generate_uuid
    )
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )
    canonical_event_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    stage: Mapped[str] = mapped_column(
        String(50), index=True
    )  # e.g., summary_generation, feedback_agent
    started_at: Mapped[datetime] = mapped_column(default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # e.g., publish, regenerate
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    __table_args__ = (Index("idx_pipeline_traces_story_stage", "story_id", "stage"),)
