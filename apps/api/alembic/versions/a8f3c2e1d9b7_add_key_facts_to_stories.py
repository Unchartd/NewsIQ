"""add_key_facts_to_stories

Revision ID: a8f3c2e1d9b7
Revises: 50cf1906f934
Create Date: 2026-06-17 16:00:00.000000

Adds a JSONB column to stories for storing key facts extracted by Gemini.
Previously these were computed by AI and immediately discarded. This migration
persists them so the API can return them in story detail responses.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8f3c2e1d9b7"
down_revision: str | None = "50cf1906f934"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add key_facts JSONB column to stories table.
    # Default NULL — existing stories will have no key_facts until re-synthesized.
    # The API returns an empty list [] when key_facts is NULL.
    op.add_column(
        "stories",
        sa.Column(
            "key_facts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Ordered list of bullet-point facts extracted by Gemini AI",
        ),
    )


def downgrade() -> None:
    op.drop_column("stories", "key_facts")
