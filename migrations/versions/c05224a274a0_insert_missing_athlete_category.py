"""insert missing athlete category

Revision ID: c05224a274a0
Revises: c4bc9d171a2e
Create Date: 2026-04-23 10:49:40.610934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision: str = 'c05224a274a0'
down_revision: Union[str, None] = 'c4bc9d171a2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    # Fetch existing categories from the database
    existing_cats_result = conn.execute(sa.text("SELECT name FROM categories")).fetchall()
    existing_cats = [row[0] for row in existing_cats_result]
    
    # The complete list of required categories based on your ApplicationCategory Enum
    required_categories = [
        "Athlete", "Coaches", "Team Officials", "Technical Officials", 
        "Medical Staff", "Media", "VIP/Guests", "LOC Staff", 
        "Volunteer", "Security", "Transport", "Service Staff"
    ]
    
    # Safely insert any missing categories
    for cat in required_categories:
        if cat not in existing_cats:
            op.execute(
                sa.text("INSERT INTO categories (id, name, created_at) VALUES (:id, :name, :created_at)")
                .bindparams(id=uuid.uuid4(), name=cat, created_at=datetime.now(timezone.utc))
            )

def downgrade() -> None:
    # Downgrading is a no-op because removing categories could break data integrity.
    # It's safer to leave the added categories in the database.
    pass