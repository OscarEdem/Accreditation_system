"""add media specific fields to applications

Revision ID: 14c7936f05ab
Revises: a1b2c3d4e5f6
Create Date: 2026-04-21 17:02:08.666568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14c7936f05ab'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('applications', sa.Column('outlet_name', sa.String(), nullable=True))
    op.add_column('applications', sa.Column('media_accreditation_type', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('applications', 'media_accreditation_type')
    op.drop_column('applications', 'outlet_name')