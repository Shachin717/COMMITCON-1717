"""add_allocation_history_table

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-10-10 05:00:00.000000+00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'allocation_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='SIMULATED'),
        sa.Column('date_from', sa.Date(), nullable=True),
        sa.Column('date_to', sa.Date(), nullable=True),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('baseline_metrics', sa.JSON(), nullable=False),
        sa.Column('optimized_metrics', sa.JSON(), nullable=False),
        sa.Column('execution_time_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_allocation_history_created_at', 'allocation_history', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_allocation_history_created_at', table_name='allocation_history')
    op.drop_table('allocation_history')

