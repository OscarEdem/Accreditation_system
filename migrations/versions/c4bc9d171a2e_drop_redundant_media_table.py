"""drop redundant media table

Revision ID: c4bc9d171a2e
Revises: 47148378224a
Create Date: 2026-04-22 17:23:20.397822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4bc9d171a2e'
down_revision: Union[str, None] = '47148378224a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Update Applications table
    op.execute("UPDATE applications SET specific_role = 'Jury of Appeal' WHERE specific_role = 'Jury';")
    op.execute("UPDATE applications SET specific_role = 'Walking Judge' WHERE specific_role = 'Race Walk Judge';")
    op.execute("UPDATE applications SET specific_role = 'NSA Deputy Director General' WHERE specific_role = 'NSA Deputy Director';")
    
    # Update Participants table
    op.execute("UPDATE participants SET role = 'Jury of Appeal' WHERE role = 'Jury';")
    op.execute("UPDATE participants SET role = 'Walking Judge' WHERE role = 'Race Walk Judge';")
    op.execute("UPDATE participants SET role = 'NSA Deputy Director General' WHERE role = 'NSA Deputy Director';")

def downgrade() -> None:
    # Reverse the changes in case you ever need to rollback
    op.execute("UPDATE applications SET specific_role = 'Jury' WHERE specific_role = 'Jury of Appeal';")
    op.execute("UPDATE applications SET specific_role = 'Race Walk Judge' WHERE specific_role = 'Walking Judge';")
    op.execute("UPDATE applications SET specific_role = 'NSA Deputy Director' WHERE specific_role = 'NSA Deputy Director General';")
    
    op.execute("UPDATE participants SET role = 'Jury' WHERE role = 'Jury of Appeal';")
    op.execute("UPDATE participants SET role = 'Race Walk Judge' WHERE role = 'Walking Judge';")
    op.execute("UPDATE participants SET role = 'NSA Deputy Director' WHERE role = 'NSA Deputy Director General';")