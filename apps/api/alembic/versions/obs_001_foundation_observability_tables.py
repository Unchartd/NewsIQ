"""Add observability tables: pipeline_runs, stage_runs, llm_traces, etc.

Revision ID: obs_001_foundation
Revises: None (head)
Create Date: 2026-06-20 14:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic
revision: str = "obs_001_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = ("observability",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all observability tables."""

    # ── prompt_versions (must be created before llm_traces due to FK) ──────
    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prompt_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("user_prompt_template", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, default=1, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_prompt_versions_hash", "prompt_versions", ["prompt_hash"])
    op.create_index("idx_prompt_versions_stage", "prompt_versions", ["stage"])
    op.create_index("idx_prompt_versions_created", "prompt_versions", ["created_at"])

    # ── pipeline_runs ──────────────────────────────────────────────────────
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("trigger", sa.String(50), default="manual", nullable=False),
        sa.Column("pipeline_type", sa.String(50), default="batch", nullable=False),
        sa.Column(
            "parent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id"),
            nullable=True,
        ),
        sa.Column("is_replay", sa.Boolean, default=False, nullable=False),
        sa.Column("status", sa.String(30), default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("total_latency_ms", sa.Float, default=0.0),
        sa.Column("total_stages", sa.Integer, default=0),
        sa.Column("successful_stages", sa.Integer, default=0),
        sa.Column("failed_stages", sa.Integer, default=0),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
    )
    op.create_index("idx_pipeline_runs_trace", "pipeline_runs", ["trace_id"])
    op.create_index("idx_pipeline_runs_started", "pipeline_runs", ["started_at"])
    op.create_index("idx_pipeline_runs_status", "pipeline_runs", ["status"])

    # ── stage_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "stage_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("latency_ms", sa.Float, default=0.0),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("error_type", sa.String(255), nullable=True),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
    )
    op.create_index("idx_stage_runs_run_id", "stage_runs", ["run_id"])
    op.create_index("idx_stage_runs_trace_id", "stage_runs", ["trace_id"])
    op.create_index("idx_stage_runs_stage", "stage_runs", ["stage"])
    op.create_index("idx_stage_runs_started", "stage_runs", ["started_at"])
    op.create_index("idx_stage_runs_run_stage", "stage_runs", ["run_id", "stage"])
    op.create_index("idx_stage_runs_story_id", "stage_runs", ["story_id"])
    op.create_index("idx_stage_runs_article_id", "stage_runs", ["article_id"])

    # ── llm_traces ─────────────────────────────────────────────────────────
    op.create_table(
        "llm_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("user_prompt", sa.Text, nullable=True),
        sa.Column("response_text", sa.Text, nullable=True),
        sa.Column("input_tokens", sa.Integer, default=0),
        sa.Column("output_tokens", sa.Integer, default=0),
        sa.Column("total_tokens", sa.Integer, default=0),
        sa.Column("latency_ms", sa.Float, default=0.0),
        sa.Column("cost_usd", sa.Float, default=0.0),
        sa.Column("temperature", sa.Float, default=0.0),
        sa.Column("status", sa.String(30), default="success"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "prompt_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_llm_traces_run_id", "llm_traces", ["run_id"])
    op.create_index("idx_llm_traces_trace_id", "llm_traces", ["trace_id"])
    op.create_index("idx_llm_traces_provider_model", "llm_traces", ["provider", "model"])
    op.create_index("idx_llm_traces_stage", "llm_traces", ["stage"])
    op.create_index("idx_llm_traces_story_id", "llm_traces", ["story_id"])
    op.create_index("idx_llm_traces_article_id", "llm_traces", ["article_id"])
    op.create_index("idx_llm_traces_created", "llm_traces", ["created_at"])

    # ── token_usage ────────────────────────────────────────────────────────
    op.create_table(
        "token_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.DateTime, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.BigInteger, default=0),
        sa.Column("output_tokens", sa.BigInteger, default=0),
        sa.Column("total_tokens", sa.BigInteger, default=0),
        sa.Column("total_cost_usd", sa.Float, default=0.0),
        sa.Column("call_count", sa.Integer, default=0),
        sa.Column("error_count", sa.Integer, default=0),
        sa.Column("avg_latency_ms", sa.Float, default=0.0),
    )
    op.create_index(
        "idx_token_usage_date_provider",
        "token_usage",
        ["date", "provider", "model"],
        unique=True,
    )

    # ── cost_records ───────────────────────────────────────────────────────
    op.create_table(
        "cost_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer, default=0),
        sa.Column("output_tokens", sa.Integer, default=0),
        sa.Column("cost_usd", sa.Float, default=0.0),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_cost_records_story_id", "cost_records", ["story_id"])
    op.create_index("idx_cost_records_article_id", "cost_records", ["article_id"])
    op.create_index("idx_cost_records_provider", "cost_records", ["provider"])
    op.create_index("idx_cost_records_created", "cost_records", ["created_at"])

    # ── retry_history ──────────────────────────────────────────────────────
    op.create_table(
        "retry_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("error_type", sa.String(255), nullable=False),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("error_traceback", sa.Text, nullable=True),
        sa.Column("wait_seconds", sa.Float, default=0.0),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_retry_history_run_id", "retry_history", ["run_id"])
    op.create_index("idx_retry_history_created", "retry_history", ["created_at"])

    # ── error_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "error_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("error_category", sa.String(50), nullable=False),
        sa.Column("error_type", sa.String(255), nullable=False),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("error_traceback", sa.Text, nullable=True),
        sa.Column("severity", sa.String(20), default="error", nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved", sa.Boolean, default=False),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_error_logs_run_id", "error_logs", ["run_id"])
    op.create_index("idx_error_logs_trace_id", "error_logs", ["trace_id"])
    op.create_index("idx_error_logs_category", "error_logs", ["error_category"])
    op.create_index("idx_error_logs_severity", "error_logs", ["severity"])
    op.create_index("idx_error_logs_story_id", "error_logs", ["story_id"])
    op.create_index("idx_error_logs_created", "error_logs", ["created_at"])

    # ── queue_metrics ──────────────────────────────────────────────────────
    op.create_table(
        "queue_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_name", sa.String(100), nullable=False),
        sa.Column("active_jobs", sa.Integer, default=0),
        sa.Column("waiting_jobs", sa.Integer, default=0),
        sa.Column("completed_jobs", sa.Integer, default=0),
        sa.Column("failed_jobs", sa.Integer, default=0),
        sa.Column("dead_letter_jobs", sa.Integer, default=0),
        sa.Column("avg_latency_ms", sa.Float, default=0.0),
        sa.Column("worker_count", sa.Integer, default=0),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_queue_metrics_captured", "queue_metrics", ["captured_at"])

    # ── human_reviews ──────────────────────────────────────────────────────
    op.create_table(
        "human_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before_value", postgresql.JSONB, nullable=True),
        sa.Column("after_value", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_human_reviews_story", "human_reviews", ["story_id"])
    op.create_index("idx_human_reviews_action", "human_reviews", ["action"])
    op.create_index("idx_human_reviews_created", "human_reviews", ["created_at"])


def downgrade() -> None:
    """Drop all observability tables in reverse dependency order."""
    op.drop_table("human_reviews")
    op.drop_table("queue_metrics")
    op.drop_table("error_logs")
    op.drop_table("retry_history")
    op.drop_table("cost_records")
    op.drop_table("token_usage")
    op.drop_table("llm_traces")
    op.drop_table("stage_runs")
    op.drop_table("pipeline_runs")
    op.drop_table("prompt_versions")
