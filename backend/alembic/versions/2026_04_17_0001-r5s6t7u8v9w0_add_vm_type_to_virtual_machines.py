"""add vm_type to virtual_machines

Revision ID: r5s6t7u8v9w0
Revises: q4w5e6r7t8y9
Create Date: 2026-04-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'r5s6t7u8v9w0'
down_revision = 'q4w5e6r7t8y9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'virtual_machines',
        sa.Column('vm_type', sa.String(10), nullable=False, server_default='qemu')
    )
    op.create_index('ix_virtual_machines_vm_type', 'virtual_machines', ['vm_type'])


def downgrade() -> None:
    op.drop_index('ix_virtual_machines_vm_type', table_name='virtual_machines')
    op.drop_column('virtual_machines', 'vm_type')
