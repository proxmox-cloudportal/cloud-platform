"""add network_id to virtual_machines

Revision ID: q4w5e6r7t8y9
Revises: p3v1n2e3t4w5
Create Date: 2026-02-08 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'q4w5e6r7t8y9'
down_revision: Union[str, None] = 'p3v1n2e3t4w5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add network_id column to virtual_machines for network assignment during provisioning."""

    # Add network_id column to virtual_machines
    op.add_column(
        'virtual_machines',
        sa.Column('network_id', sa.String(36), nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_vms_network_id',
        'virtual_machines',
        'vpc_networks',
        ['network_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add index for faster lookups
    op.create_index('idx_vms_network_id', 'virtual_machines', ['network_id'])


def downgrade() -> None:
    """Remove network_id column from virtual_machines."""

    op.drop_index('idx_vms_network_id', table_name='virtual_machines')
    op.drop_constraint('fk_vms_network_id', 'virtual_machines', type_='foreignkey')
    op.drop_column('virtual_machines', 'network_id')
