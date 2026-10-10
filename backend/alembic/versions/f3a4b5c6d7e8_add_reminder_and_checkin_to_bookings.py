"""add_reminder_and_checkin_to_bookings

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-10-10 01:20:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'bookings',
        sa.Column('reminder_sent', sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column(
        'bookings',
        sa.Column('checked_in', sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    # Additional performance indexes
    op.create_index('ix_rooms_capacity', 'rooms', ['capacity'], unique=False)
    op.create_index('ix_audit_logs_entity_id', 'audit_logs', ['entity_id'], unique=False)
    op.create_index('ix_users_is_active', 'users', ['is_active'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_index('ix_audit_logs_entity_id', table_name='audit_logs')
    op.drop_index('ix_rooms_capacity', table_name='rooms')
    op.drop_column('bookings', 'checked_in')
    op.drop_column('bookings', 'reminder_sent')

