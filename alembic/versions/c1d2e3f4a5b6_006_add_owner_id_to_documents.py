"""006_add_owner_id_to_documents

Revision ID: c1d2e3f4a5b6
Revises: b8c7d6e5f4a3
Create Date: 2026-09-04 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b8c7d6e5f4a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'documents',
        sa.Column('owner_id', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_documents_owner_id', 'documents', ['owner_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_documents_owner_id', table_name='documents')
    op.drop_column('documents', 'owner_id')
