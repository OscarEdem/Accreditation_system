"""drop redundant media table

Revision ID: 47148378224a
Revises: 14c7936f05ab
Create Date: 2026-04-21 17:04:58.901504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '47148378224a'
down_revision: Union[str, None] = '14c7936f05ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.drop_table('media')

def downgrade() -> None:
    op.create_table('media',
        sa.Column('application_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('outlet_name', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('accreditation_type', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], name='media_application_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='media_pkey')
    )