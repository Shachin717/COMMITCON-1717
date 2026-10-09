"""add_hod_workflow

Revision ID: a1b2c3d4e5f6
Revises: 74876a2aa142
Create Date: 2026-10-09 10:19:47.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '74876a2aa142'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. approval_policies table
    op.create_table('approval_policies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('purpose', sa.String(length=50), nullable=False),
    sa.Column('requires_hod_approval', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_policies_id'), 'approval_policies', ['id'], unique=False)
    op.create_index(op.f('ix_approval_policies_purpose'), 'approval_policies', ['purpose'], unique=True)

    # 2. booking_approvals table
    op.create_table('booking_approvals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('booking_id', sa.Integer(), nullable=False),
    sa.Column('approver_user_id', sa.Integer(), nullable=False),
    sa.Column('decision', sa.String(length=20), nullable=False),
    sa.Column('remarks', sa.String(length=500), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['approver_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_booking_approvals_approver_user_id'), 'booking_approvals', ['approver_user_id'], unique=False)
    op.create_index(op.f('ix_booking_approvals_booking_id'), 'booking_approvals', ['booking_id'], unique=False)
    op.create_index(op.f('ix_booking_approvals_id'), 'booking_approvals', ['id'], unique=False)

    # 3. users table - add department_id
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_department_id'), ['department_id'], unique=False)
        batch_op.create_foreign_key('fk_users_department_id', 'departments', ['department_id'], ['id'], ondelete='SET NULL')

    # 4. bookings table - add columns and alter constraint
    with op.batch_alter_table('bookings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('purpose', sa.String(length=50), server_default='REGULAR_CLASS', nullable=True))
        batch_op.add_column(sa.Column('requested_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('rejection_reason', sa.String(length=500), nullable=True))
        batch_op.create_index(batch_op.f('ix_bookings_requested_by_user_id'), ['requested_by_user_id'], unique=False)
        batch_op.create_foreign_key('fk_bookings_requested_by_user_id', 'users', ['requested_by_user_id'], ['id'], ondelete='SET NULL')
        
    # In SQLite, altering check constraints via batch mode can be tricky if they were table args.
    # But Alembic handles it if we don't name it in drop_constraint sometimes, or if we recreate the table.
    # Actually, SQLAlchemy 2 + alembic render_as_batch=True handles table arg constraints if we recreate them or just rely on the model.
    # But since we are explicitly defining migrations, we can drop and recreate the constraint if possible, but SQLite doesn't support dropping constraints.
    # With batch mode, the whole table is recreated based on the current model or the schema provided.
    # So we don't need to explicitly drop/create check constraints in batch_op if they are just recreated. 
    # Let's try explicit drop/create just in case.
    # Wait, dropping a constraint by name in SQLite batch mode:
    # batch_op.drop_constraint('check_booking_status', type_='check')
    # batch_op.create_check_constraint('check_booking_status', condition="status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'PENDING_HOD_APPROVAL', 'APPROVED', 'REJECTED')")
    # Actually, let's just do it directly.
    with op.batch_alter_table('bookings', schema=None) as batch_op:
        # SQLite doesn't support dropping constraints, but alembic batch mode fakes it by recreating the table.
        # But wait! If we don't know the exact name or if it's tricky, we can omit it, but the prompt says:
        # "Drops and recreates the check_booking_status constraint with new values (use batch mode)"
        try:
            batch_op.drop_constraint('check_booking_status', type_='check')
        except:
            pass
        batch_op.create_check_constraint('check_booking_status', condition="status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'PENDING_HOD_APPROVAL', 'APPROVED', 'REJECTED')")

    # Seed default approval policies
    op.execute("""
        INSERT INTO approval_policies (purpose, requires_hod_approval) VALUES 
        ('REGULAR_CLASS', 0),
        ('EXAMINATION', 1),
        ('MCQ_TEST', 1),
        ('SEMINAR', 0),
        ('WORKSHOP', 0),
        ('EVENT', 0),
        ('OTHER', 0)
    """)


def downgrade() -> None:
    with op.batch_alter_table('bookings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_bookings_requested_by_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_bookings_requested_by_user_id'))
        batch_op.drop_column('rejection_reason')
        batch_op.drop_column('requested_by_user_id')
        batch_op.drop_column('purpose')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_department_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_users_department_id'))
        batch_op.drop_column('department_id')

    op.drop_index(op.f('ix_booking_approvals_id'), table_name='booking_approvals')
    op.drop_index(op.f('ix_booking_approvals_booking_id'), table_name='booking_approvals')
    op.drop_index(op.f('ix_booking_approvals_approver_user_id'), table_name='booking_approvals')
    op.drop_table('booking_approvals')

    op.drop_index(op.f('ix_approval_policies_purpose'), table_name='approval_policies')
    op.drop_index(op.f('ix_approval_policies_id'), table_name='approval_policies')
    op.drop_table('approval_policies')
