"""add ai execution records table

Revision ID: a2c3d4e5f6a8
Revises: a1b2c3d4e5f6
Create Date: 2026-07-16 02:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic
revision: str = "a2c3d4e5f6a8"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_execution_records",
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("capability", sa.String(length=100), nullable=True),
        sa.Column("prompt_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallback_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("schema_repaired", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("decision", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        # Phase 6 fields
        sa.Column("unsupported_claims_count", sa.Integer(), nullable=True),
        sa.Column("missing_citations_count", sa.Integer(), nullable=True),
        sa.Column("contradictions_count", sa.Integer(), nullable=True),
        sa.Column("bias_corrections_count", sa.Integer(), nullable=True),
        sa.Column("regeneration_count", sa.Integer(), nullable=True),
        sa.Column("reflection_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("execution_id"),
    )
    op.create_index("idx_ai_execution_records_trace_id", "ai_execution_records", ["trace_id"])
    op.create_index("idx_ai_execution_records_story_id", "ai_execution_records", ["story_id"])
    op.create_index("idx_ai_execution_records_article_id", "ai_execution_records", ["article_id"])
    op.create_index("idx_ai_execution_records_stage", "ai_execution_records", ["stage"])
    op.create_index("idx_ai_execution_records_created_at", "ai_execution_records", ["created_at"])
    op.create_index(
        "idx_ai_execution_records_story_stage", "ai_execution_records", ["story_id", "stage"]
    )
    op.create_index(
        "idx_ai_execution_records_prompt_version",
        "ai_execution_records",
        ["prompt_name", "prompt_version"],
    )
    op.create_index(
        "idx_ai_execution_records_model_provider", "ai_execution_records", ["model", "provider"]
    )


def downgrade() -> None:
    op.drop_index("idx_ai_execution_records_model_provider", table_name="ai_execution_records")
    op.drop_index("idx_ai_execution_records_prompt_version", table_name="ai_execution_records")
    op.drop_index("idx_ai_execution_records_story_stage", table_name="ai_execution_records")
    op.drop_index("idx_ai_execution_records_created_at", table_name="ai_execution_records")
    op.drop_index("idx_ai_execution_records_stage", table_name="ai_execution_records")
    op.drop_index("idx_ai_execution_records_article_id", table_name="ai_execution_records")
    op.drop_index("idx_ai_execution_records_story_id", table_name="ai_execution_records")
    op.drop_index("idx_ai_execution_records_trace_id", table_name="ai_execution_records")
    op.drop_table("ai_execution_records")
