"""add_waitlist_entries
Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-09 21:40:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'waitlist_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('slot_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('roll_no', sa.String(length=50), nullable=True),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('class_name', sa.String(length=100), nullable=True),
        sa.Column('notified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_id'], ['time_slots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_waitlist_entries_room_id'), 'waitlist_entries', ['room_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_date'), 'waitlist_entries', ['date'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_slot_id'), 'waitlist_entries', ['slot_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_email'), 'waitlist_entries', ['email'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_notified'), 'waitlist_entries', ['notified'], unique=False)
    op.create_index('ix_waitlist_room_date_slot_notified', 'waitlist_entries', ['room_id', 'date', 'slot_id', 'notified'], unique=False)


def downgrade() -> None:
    op.drop_table('waitlist_entries')

