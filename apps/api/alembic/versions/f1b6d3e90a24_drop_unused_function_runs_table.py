"""drop the unused function_runs table

FunctionRunModel had no writer, no reader, and no endpoint — its only references
anywhere in the codebase were its own re-exports in app/models/__init__.py — and
the table holds 0 rows in production. Removing the model without dropping the
table would leave the schema and the models permanently out of step, so the next
autogenerate would produce a surprise diff.

This is the only observability table removed. The other five empty ones are kept
deliberately:

  * error_logs, token_usage, cost_records — the natural destinations for gaps the
    audit found (durable logs, token capture, cost records). Dropping them would
    remove the obvious place to put the fix.
  * retry_history — no writer, but referenced by the purge task; low value to
    remove and it costs nothing to keep.
  * human_reviews — NOT dead. admin_service constructs rows from
    POST /admin/review/{story_id}/action, which the frontend calls. Zero rows
    means unused, not unreachable.

Reversible: downgrade recreates the table exactly. Nothing is lost either way,
because there is no data.

Revision ID: f1b6d3e90a24
Revises: e4a7c9b21d35
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1b6d3e90a24"
down_revision: str | None = "e4a7c9b21d35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("function_runs")


def downgrade() -> None:
    op.create_table(
        "function_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("function_name", sa.String(length=255), nullable=False),
        sa.Column("caller", sa.String(length=255), nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("span_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_function_runs_function_name", "function_runs", ["function_name"])
    op.create_index("ix_function_runs_run_id", "function_runs", ["run_id"])
    op.create_index("ix_function_runs_trace_id", "function_runs", ["trace_id"])
    op.create_index("ix_function_runs_span_id", "function_runs", ["span_id"])
    op.create_index("ix_function_runs_created_at", "function_runs", ["created_at"])
