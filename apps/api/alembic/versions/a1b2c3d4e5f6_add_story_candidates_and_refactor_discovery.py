"""add_story_candidates_and_refactor_discovery

Revision ID: a1b2c3d4e5f6
Revises: 1af5d702f838
Create Date: 2026-07-15 11:10:00.000000

Changes:
    1. Create `story_candidates` table.
    2. Add `story_candidate_id` (nullable FK) to `discovery_tasks`.
    3. Make `discovery_tasks.article_id` nullable (SET NULL, was CASCADE NOT NULL).
    4. Add `story_candidate_id` (nullable FK) to `crawl_tasks`.
    5. Add `tier` column (Integer, default=3) to `crawl_tasks`.

All new columns are nullable with defaults. No existing rows are broken.
No data migration required.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "62039cc3c6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create story_candidates
    op.create_table(
        "story_candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("date_bucket", sa.String(length=10), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column(
            "discovery_provider", sa.String(length=50), nullable=False, server_default="google_rss"
        ),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="collecting"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("priority_reason", sa.String(length=100), nullable=True),
        sa.Column("rss_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rss_source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("collect_until", sa.DateTime(), nullable=True),
        sa.Column("search_dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("search_completed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("urls_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("urls_crawled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_persisted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_clustered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("story_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_hash", "date_bucket", name="uq_story_candidate_query_date"),
    )
    op.create_index("idx_story_candidates_status", "story_candidates", ["status"])
    op.create_index("idx_story_candidates_collect_until", "story_candidates", ["collect_until"])
    op.create_index("idx_story_candidates_created", "story_candidates", ["created_at"])
    op.create_index("idx_story_candidates_priority", "story_candidates", ["priority", "created_at"])
    op.create_index(op.f("ix_story_candidates_query_hash"), "story_candidates", ["query_hash"])
    op.create_index(op.f("ix_story_candidates_story_id"), "story_candidates", ["story_id"])

    # 2. Add story_candidate_id to discovery_tasks
    op.add_column("discovery_tasks", sa.Column("story_candidate_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_discovery_tasks_story_candidate_id",
        "discovery_tasks",
        "story_candidates",
        ["story_candidate_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_discovery_tasks_story_candidate_id"),
        "discovery_tasks",
        ["story_candidate_id"],
    )

    # 3. Make discovery_tasks.article_id nullable (legacy compat)
    op.drop_constraint("discovery_tasks_article_id_fkey", "discovery_tasks", type_="foreignkey")
    op.alter_column("discovery_tasks", "article_id", nullable=True)
    op.create_foreign_key(
        "fk_discovery_tasks_article_id",
        "discovery_tasks",
        "articles",
        ["article_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Add story_candidate_id to crawl_tasks
    op.add_column("crawl_tasks", sa.Column("story_candidate_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_crawl_tasks_story_candidate_id",
        "crawl_tasks",
        "story_candidates",
        ["story_candidate_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_crawl_tasks_story_candidate", "crawl_tasks", ["story_candidate_id"])

    # 5. Add tier column to crawl_tasks
    op.add_column(
        "crawl_tasks", sa.Column("tier", sa.Integer(), nullable=False, server_default="3")
    )
    op.create_index("idx_crawl_tasks_tier", "crawl_tasks", ["tier"])


def downgrade() -> None:
    op.drop_index("idx_crawl_tasks_tier", table_name="crawl_tasks")
    op.drop_column("crawl_tasks", "tier")

    op.drop_index("idx_crawl_tasks_story_candidate", table_name="crawl_tasks")
    op.drop_constraint("fk_crawl_tasks_story_candidate_id", "crawl_tasks", type_="foreignkey")
    op.drop_column("crawl_tasks", "story_candidate_id")

    op.drop_constraint("fk_discovery_tasks_article_id", "discovery_tasks", type_="foreignkey")
    op.alter_column("discovery_tasks", "article_id", nullable=False)
    op.create_foreign_key(
        "discovery_tasks_article_id_fkey",
        "discovery_tasks",
        "articles",
        ["article_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_index(op.f("ix_discovery_tasks_story_candidate_id"), table_name="discovery_tasks")
    op.drop_constraint(
        "fk_discovery_tasks_story_candidate_id", "discovery_tasks", type_="foreignkey"
    )
    op.drop_column("discovery_tasks", "story_candidate_id")

    op.drop_index(op.f("ix_story_candidates_story_id"), table_name="story_candidates")
    op.drop_index(op.f("ix_story_candidates_query_hash"), table_name="story_candidates")
    op.drop_index("idx_story_candidates_priority", table_name="story_candidates")
    op.drop_index("idx_story_candidates_created", table_name="story_candidates")
    op.drop_index("idx_story_candidates_collect_until", table_name="story_candidates")
    op.drop_index("idx_story_candidates_status", table_name="story_candidates")
    op.drop_table("story_candidates")
