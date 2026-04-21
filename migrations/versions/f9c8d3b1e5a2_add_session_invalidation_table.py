"""add session invalidation table for persistent logout tracking

Revision ID: f9c8d3b1e5a2
Revises: eb45fc6d7341
Create Date: 2026-04-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f9c8d3b1e5a2'
down_revision: Union[str, None] = 'eb45fc6d7341'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create session_invalidations table
    op.create_table(
        'session_invalidations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('invalidated_at', sa.DateTime(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index(
        'ix_session_invalidations_user_id',
        'session_invalidations',
        ['user_id']
    )
    op.create_index(
        'ix_session_invalidations_session_id',
        'session_invalidations',
        ['session_id']
    )
    op.create_index(
        'ix_session_invalidations_invalidated_at',
        'session_invalidations',
        ['invalidated_at']
    )
    op.create_index(
        'ix_session_invalidations_user_session',
        'session_invalidations',
        ['user_id', 'session_id']
    )


def downgrade() -> None:
    op.drop_index('ix_session_invalidations_user_session', table_name='session_invalidations')
    op.drop_index('ix_session_invalidations_invalidated_at', table_name='session_invalidations')
    op.drop_index('ix_session_invalidations_session_id', table_name='session_invalidations')
    op.drop_index('ix_session_invalidations_user_id', table_name='session_invalidations')
    op.drop_table('session_invalidations')
