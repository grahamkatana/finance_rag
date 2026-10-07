"""011_create_usage_tables

Revision ID: b9c8d7e6f5a4
Revises: a7b8c9d0e1f2
Create Date: 2026-10-07 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9c8d7e6f5a4'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usage_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('provider', sa.String(40), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index('ix_usage_events_created_at', 'usage_events', ['created_at'])
    op.create_table(
        'model_prices',
        sa.Column('provider', sa.String(40), primary_key=True),
        sa.Column('model', sa.String(100), primary_key=True),
        sa.Column('input_per_million', sa.Numeric(12, 4), nullable=False),
        sa.Column('output_per_million', sa.Numeric(12, 4), nullable=False),
        sa.Column('note', sa.String(200), nullable=False, server_default=''),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'provider_credits',
        sa.Column('provider', sa.String(40), primary_key=True),
        sa.Column('amount_usd', sa.Numeric(12, 4), nullable=False),
        sa.Column('as_of', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # text-embedding-3-small has been $0.02 per million tokens since launch; check it against the OpenAI pricing page.
    op.execute("INSERT INTO model_prices (provider, model, input_per_million, output_per_million, note) "
               "VALUES ('openai', 'text-embedding-3-small', 0.02, 0, 'seeded; confirm on the OpenAI pricing page')")


def downgrade() -> None:
    op.drop_table('provider_credits')
    op.drop_table('model_prices')
    op.drop_index('ix_usage_events_created_at', table_name='usage_events')
    op.drop_table('usage_events')
