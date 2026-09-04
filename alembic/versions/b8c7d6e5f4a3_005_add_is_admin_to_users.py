"""005_add_is_admin_to_users

Revision ID: b8c7d6e5f4a3
Revises: f7a3b2c1d0e9
Create Date: 2026-09-04 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c7d6e5f4a3'
down_revision: Union[str, Sequence[str], None] = 'f7a3b2c1d0e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_admin')
