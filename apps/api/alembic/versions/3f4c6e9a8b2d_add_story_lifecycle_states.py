"""add_story_lifecycle_states

Revision ID: 3f4c6e9a8b2d
Revises: 89b3664b943f
Create Date: 2026-07-10 09:18:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '3f4c6e9a8b2d'
down_revision = '89b3664b943f'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add new columns to 'stories' table
    op.add_column('stories', sa.Column('lifecycle_state', sa.String(length=30), nullable=False, server_default='emerging'))
    op.add_column('stories', sa.Column('canonical_event_id', sa.String(length=100), nullable=True))
    op.add_column('stories', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('stories', sa.Column('transition_reason', sa.Text(), nullable=True))
    op.add_column('stories', sa.Column('lifecycle_changed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')))
    op.add_column('stories', sa.Column('last_discovery_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('stories', sa.Column('last_significant_update_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')))
    op.add_column('stories', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('stories', sa.Column('confidence_score', sa.Float(), nullable=True))
    op.add_column('stories', sa.Column('freshness_score', sa.Float(), nullable=True))
    op.add_column('stories', sa.Column('source_diversity_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('stories', sa.Column('contradiction_score', sa.Float(), nullable=True))

    # Create indexes for the new columns
    op.create_index(op.f('ix_stories_lifecycle_state'), 'stories', ['lifecycle_state'], unique=False)
    op.create_index(op.f('ix_stories_canonical_event_id'), 'stories', ['canonical_event_id'], unique=False)
    op.create_index(op.f('ix_stories_lifecycle_changed_at'), 'stories', ['lifecycle_changed_at'], unique=False)
    op.create_index(op.f('ix_stories_last_discovery_at'), 'stories', ['last_discovery_at'], unique=False)
    op.create_index(op.f('ix_stories_confidence_score'), 'stories', ['confidence_score'], unique=False)
    op.create_index(op.f('ix_stories_freshness_score'), 'stories', ['freshness_score'], unique=False)
    op.create_index(op.f('ix_stories_source_diversity_count'), 'stories', ['source_diversity_count'], unique=False)
    op.create_index(op.f('ix_stories_contradiction_score'), 'stories', ['contradiction_score'], unique=False)

def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_stories_contradiction_score'), table_name='stories')
    op.drop_index(op.f('ix_stories_source_diversity_count'), table_name='stories')
    op.drop_index(op.f('ix_stories_freshness_score'), table_name='stories')
    op.drop_index(op.f('ix_stories_confidence_score'), table_name='stories')
    op.drop_index(op.f('ix_stories_last_discovery_at'), table_name='stories')
    op.drop_index(op.f('ix_stories_lifecycle_changed_at'), table_name='stories')
    op.drop_index(op.f('ix_stories_canonical_event_id'), table_name='stories')
    op.drop_index(op.f('ix_stories_lifecycle_state'), table_name='stories')

    # Drop columns
    op.drop_column('stories', 'contradiction_score')
    op.drop_column('stories', 'source_diversity_count')
    op.drop_column('stories', 'freshness_score')
    op.drop_column('stories', 'confidence_score')
    op.drop_column('stories', 'archived_at')
    op.drop_column('stories', 'last_significant_update_at')
    op.drop_column('stories', 'last_discovery_at')
    op.drop_column('stories', 'lifecycle_changed_at')
    op.drop_column('stories', 'transition_reason')
    op.drop_column('stories', 'version')
    op.drop_column('stories', 'canonical_event_id')
    op.drop_column('stories', 'lifecycle_state')
