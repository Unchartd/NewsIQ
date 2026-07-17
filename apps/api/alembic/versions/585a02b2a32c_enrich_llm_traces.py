"""enrich_llm_traces

Revision ID: 585a02b2a32c
Revises: a2c3d4e5f6a8
Create Date: 2026-07-17 04:06:51.738972
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '585a02b2a32c'
down_revision: Union[str, None] = 'a2c3d4e5f6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_traces", sa.Column("stage_run_id", sa.UUID(), nullable=True))
    op.add_column("llm_traces", sa.Column("parent_llm_trace_id", sa.UUID(), nullable=True))

    op.create_foreign_key(
        "fk_llm_traces_stage_run_id",
        "llm_traces",
        "stage_runs",
        ["stage_run_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_llm_traces_parent_llm_trace_id",
        "llm_traces",
        "llm_traces",
        ["parent_llm_trace_id"],
        ["id"],
        ondelete="SET NULL"
    )

    op.create_index("idx_llm_traces_stage_run_id", "llm_traces", ["stage_run_id"])
    op.create_index("idx_llm_traces_parent_llm_trace_id", "llm_traces", ["parent_llm_trace_id"])


def downgrade() -> None:
    op.drop_index("idx_llm_traces_parent_llm_trace_id", table_name="llm_traces")
    op.drop_index("idx_llm_traces_stage_run_id", table_name="llm_traces")

    op.drop_constraint("fk_llm_traces_parent_llm_trace_id", "llm_traces", type_="foreignkey")
    op.drop_constraint("fk_llm_traces_stage_run_id", "llm_traces", type_="foreignkey")

    op.drop_column("llm_traces", "parent_llm_trace_id")
    op.drop_column("llm_traces", "stage_run_id")
