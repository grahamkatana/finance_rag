"""007_create_document_shares

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-09-04 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'document_shares',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('granted_to_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_name', 'granted_to_user_id', name='uq_document_shares_file_user'),
    )
    op.create_index('ix_document_shares_file_name', 'document_shares', ['file_name'])
    op.create_index('ix_document_shares_owner_id', 'document_shares', ['owner_id'])
    op.create_index('ix_document_shares_granted_to_user_id', 'document_shares', ['granted_to_user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_document_shares_granted_to_user_id', table_name='document_shares')
    op.drop_index('ix_document_shares_owner_id', table_name='document_shares')
    op.drop_index('ix_document_shares_file_name', table_name='document_shares')
    op.drop_table('document_shares')
