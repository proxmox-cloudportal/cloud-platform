"""Make VM organization_id required

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-01-31 18:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make organization_id NOT NULL on virtual_machines table."""

    # Verify no VMs have NULL organization_id before making it required
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT COUNT(*) FROM virtual_machines WHERE organization_id IS NULL")
    )
    null_count = result.scalar()

    if null_count > 0:
        raise Exception(
            f"Cannot make organization_id NOT NULL: {null_count} VMs still have NULL organization_id. "
            "Run the previous migration (migrate_existing_data_to_default_org) first."
        )

    # Make organization_id NOT NULL
    # Note: MySQL syntax for modifying column to NOT NULL
    op.alter_column(
        'virtual_machines',
        'organization_id',
        existing_type=sa.String(length=36),
        nullable=False,
        existing_nullable=True
    )

    print("Made organization_id required on virtual_machines table")


def downgrade() -> None:
    """Make organization_id nullable again on virtual_machines table."""

    # Make organization_id nullable
    op.alter_column(
        'virtual_machines',
        'organization_id',
        existing_type=sa.String(length=36),
        nullable=True,
        existing_nullable=False
    )

    print("Made organization_id nullable on virtual_machines table")
