"""add deduplication columns

Revision ID: b2c3d4e5f6a7
Revises: 3f4c6e9a8b2d
Create Date: 2026-07-10 15:38:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | None = '3f4c6e9a8b2d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Phase B2: Deduplication and Fingerprinting
    op.add_column('articles', sa.Column('url_hash', sa.String(length=64), nullable=True))
    op.add_column('articles', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.add_column('articles', sa.Column('semantic_hash', sa.String(length=64), nullable=True))
    op.add_column('articles', sa.Column('fingerprint_version', sa.Integer(), server_default='1', nullable=False))
    op.add_column('articles', sa.Column('duplicate_of_article_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('articles', sa.Column('version', sa.Integer(), server_default='1', nullable=False))

    op.create_foreign_key(None, 'articles', 'articles', ['duplicate_of_article_id'], ['id'])

    op.create_index(op.f('ix_articles_url_hash'), 'articles', ['url_hash'], unique=True)
    op.create_index(op.f('ix_articles_content_hash'), 'articles', ['content_hash'], unique=False)
    op.create_index('idx_articles_content_hash', 'articles', ['content_hash'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_articles_content_hash', table_name='articles')
    op.drop_index(op.f('ix_articles_content_hash'), table_name='articles')
    op.drop_index(op.f('ix_articles_url_hash'), table_name='articles')

    op.drop_constraint(None, 'articles', type_='foreignkey')

    op.drop_column('articles', 'version')
    op.drop_column('articles', 'duplicate_of_article_id')
    op.drop_column('articles', 'fingerprint_version')
    op.drop_column('articles', 'semantic_hash')
    op.drop_column('articles', 'content_hash')
    op.drop_column('articles', 'url_hash')
