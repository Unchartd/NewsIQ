"""add prompt platform columns

Revision ID: a5f3c2e1d9c8
Revises: 1af5d702f838
Create Date: 2026-07-14 03:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a5f3c2e1d9c8'
down_revision: Union[str, None] = '1af5d702f838'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prompt_versions', sa.Column('prompt_uri', sa.String(length=255), nullable=True))
    op.add_column('prompt_versions', sa.Column('schema_version', sa.String(length=50), nullable=True))
    op.add_column('prompt_versions', sa.Column('preferred_model', sa.String(length=100), nullable=True))
    op.add_column('prompt_versions', sa.Column('lifecycle_state', sa.String(length=50), nullable=True, server_default='production'))
    op.add_column('prompt_versions', sa.Column('parent_uri', sa.String(length=255), nullable=True))
    op.add_column('prompt_versions', sa.Column('deprecated_at', sa.DateTime(), nullable=True))
    op.add_column('prompt_versions', sa.Column('deprecated_reason', sa.Text(), nullable=True))
    op.add_column('prompt_versions', sa.Column('superseded_by', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('prompt_versions', 'superseded_by')
    op.drop_column('prompt_versions', 'deprecated_reason')
    op.drop_column('prompt_versions', 'deprecated_at')
    op.drop_column('prompt_versions', 'parent_uri')
    op.drop_column('prompt_versions', 'lifecycle_state')
    op.drop_column('prompt_versions', 'preferred_model')
    op.drop_column('prompt_versions', 'schema_version')
    op.drop_column('prompt_versions', 'prompt_uri')
