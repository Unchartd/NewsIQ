"""Add article_entities table and event_fingerprint column.

Per-article entity extraction enables entity overlap as a clustering signal.
Event fingerprint enables dedup-based pre-grouping before HDBSCAN.

Revision ID: c7e1f4a2b836
Revises: obs_001_foundation_observability_tables
Create Date: 2026-06-22 07:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "c7e1f4a2b836"
down_revision = "obs_001_foundation_observability_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- New table: article_entities ---
    op.create_table(
        "article_entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "canonical_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("canonical_entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_value", sa.String(255), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_article_entities_article", "article_entities", ["article_id"])
    op.create_index(
        "idx_article_entities_canonical", "article_entities", ["canonical_entity_id"]
    )

    # --- New column: article_events.event_fingerprint ---
    op.add_column(
        "article_events",
        sa.Column("event_fingerprint", sa.String(128), nullable=True),
    )
    op.create_index(
        "idx_article_events_fingerprint", "article_events", ["event_fingerprint"]
    )


def downgrade() -> None:
    op.drop_index("idx_article_events_fingerprint", table_name="article_events")
    op.drop_column("article_events", "event_fingerprint")
    op.drop_index("idx_article_entities_canonical", table_name="article_entities")
    op.drop_index("idx_article_entities_article", table_name="article_entities")
    op.drop_table("article_entities")
