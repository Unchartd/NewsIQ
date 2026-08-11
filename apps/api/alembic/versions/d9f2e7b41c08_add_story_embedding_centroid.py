"""add stories.story_embedding centroid column

Stage B (event_validation_service.validate_stage_b) compares an incoming
article's embedding against StoryAnchor.centroid_vector, which
clustering_service read via getattr(story, "story_embedding", None). No such
column existed, so the getattr default silently returned None on every
candidate, cosine similarity was always 0.0, and Stage B could never return
PASS or MAYBE — the incremental merge path rejected 100% of articles.

Nullable and additive: existing stories start with NULL and are backfilled
lazily by clustering_service.refresh_story_centroid as articles are merged.

Revision ID: d9f2e7b41c08
Revises: 7578d7e9c7dc
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d9f2e7b41c08"
down_revision: str | None = "7578d7e9c7dc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stories",
        sa.Column("story_embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stories", "story_embedding")
