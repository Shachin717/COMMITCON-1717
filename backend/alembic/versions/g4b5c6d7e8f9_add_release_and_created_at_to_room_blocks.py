"""add_release_and_created_at_to_room_blocks

Revision ID: g4b5c6d7e8f9
Revises: a1b2c3d4e5f6
Create Date: 2026-10-10 05:55:00.000000+00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g4b5c6d7e8f9'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('room_blocks', sa.Column('is_released', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('room_blocks', sa.Column('released_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('room_blocks', sa.Column('released_by', sa.Integer(), nullable=True))
    op.add_column('room_blocks', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index(op.f('ix_room_blocks_is_released'), 'room_blocks', ['is_released'], unique=False)
    op.create_index(op.f('ix_room_blocks_released_by'), 'room_blocks', ['released_by'], unique=False)
    op.create_foreign_key('fk_room_blocks_released_by_users', 'room_blocks', 'users', ['released_by'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_room_blocks_released_by_users', 'room_blocks', type_='foreignkey')
    op.drop_index(op.f('ix_room_blocks_released_by'), table_name='room_blocks')
    op.drop_index(op.f('ix_room_blocks_is_released'), table_name='room_blocks')
    op.drop_column('room_blocks', 'created_at')
    op.drop_column('room_blocks', 'released_by')
    op.drop_column('room_blocks', 'released_at')
    op.drop_column('room_blocks', 'is_released')

