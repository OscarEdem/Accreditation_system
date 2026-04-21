"""add token blacklist table for replay attack prevention

Revision ID: a1b2c3d4e5f6
Revises: f9c8d3b1e5a2
Create Date: 2026-04-21 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f9c8d3b1e5a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create token_blacklist table
    op.create_table(
        'token_blacklist',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('token_type', sa.String(length=50), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('consumed_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    
    # Create indexes for efficient querying
    op.create_index(
        'ix_token_blacklist_token_hash',
        'token_blacklist',
        ['token_hash']
    )
    op.create_index(
        'ix_token_blacklist_user_id',
        'token_blacklist',
        ['user_id']
    )
    op.create_index(
        'ix_token_blacklist_expires_at',
        'token_blacklist',
        ['expires_at']
    )
    op.create_index(
        'ix_token_blacklist_expires_at_type',
        'token_blacklist',
        ['expires_at', 'token_type']
    )


def downgrade() -> None:
    op.drop_index('ix_token_blacklist_expires_at_type', table_name='token_blacklist')
    op.drop_index('ix_token_blacklist_expires_at', table_name='token_blacklist')
    op.drop_index('ix_token_blacklist_user_id', table_name='token_blacklist')
    op.drop_index('ix_token_blacklist_token_hash', table_name='token_blacklist')
    op.drop_table('token_blacklist')
