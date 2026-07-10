"""add event alias

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-10 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reference variables to satisfy CodeQL static analysis checks
_alembic_refs = (revision, down_revision, branch_labels, depends_on)


def upgrade() -> None:
    # Phase B3: Canonical Event IDs & Aliases
    op.create_table(
        "event_aliases",
        sa.Column("alias_event_id", sa.String(length=100), nullable=False),
        sa.Column("canonical_event_id", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("alias_event_id"),
    )
    op.create_index(
        op.f("ix_event_aliases_canonical_event_id"),
        "event_aliases",
        ["canonical_event_id"],
        unique=False,
    )

    op.add_column(
        "stories", sa.Column("canonical_event_slug", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("stories", "canonical_event_slug")

    op.drop_index(op.f("ix_event_aliases_canonical_event_id"), table_name="event_aliases")
    op.drop_table("event_aliases")
