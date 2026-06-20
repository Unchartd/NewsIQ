"""Add article_events table and event_extraction_status to articles.

Revision ID: b4e7a1c3d5f9
Revises: a8f3c2e1d9b7
Create Date: 2026-06-20 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "b4e7a1c3d5f9"
down_revision = "3efcc4470451"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New table: article_events ──────────────────────────────────────────────
    op.create_table(
        "article_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), default=True, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_type_canonical", sa.String(100), nullable=True),
        sa.Column("actors", JSONB, nullable=True),
        sa.Column("targets", JSONB, nullable=True),
        sa.Column("objects", JSONB, nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("event_time", sa.DateTime(), nullable=True),
        sa.Column("event_time_raw", sa.String(255), nullable=True),
        sa.Column("numbers", JSONB, nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_article_events_type", "article_events", ["event_type_canonical"])
    op.create_index("idx_article_events_article", "article_events", ["article_id"])

    # ── Add event_extraction_status to articles table ──────────────────────────
    op.add_column(
        "articles",
        sa.Column("event_extraction_status", sa.String(30), nullable=True, server_default="pending"),
    )

    # ── Widen story_entities.entity_type from VARCHAR(30) to VARCHAR(50) ───────
    op.alter_column(
        "story_entities",
        "entity_type",
        type_=sa.String(50),
        existing_type=sa.String(30),
    )


def downgrade() -> None:
    op.alter_column(
        "story_entities",
        "entity_type",
        type_=sa.String(30),
        existing_type=sa.String(50),
    )
    op.drop_column("articles", "event_extraction_status")
    op.drop_index("idx_article_events_article", table_name="article_events")
    op.drop_index("idx_article_events_type", table_name="article_events")
    op.drop_table("article_events")
