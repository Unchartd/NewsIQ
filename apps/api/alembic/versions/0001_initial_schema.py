"""Initial schema for NewsIQ platform.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-13

Creates the full schema directly from SQLAlchemy metadata so that fresh
environments can be provisioned without an existing database.
"""

from alembic import op

from app.core.database import Base
from app.models import models  # noqa: F401 — ensures all tables register on Base.metadata

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables from the current SQLAlchemy metadata."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop all tables."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
