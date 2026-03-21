"""add verify_ssl to proxmox_clusters

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-01-31 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add verify_ssl column to proxmox_clusters table."""
    # Add verify_ssl column with default value of False
    op.add_column(
        'proxmox_clusters',
        sa.Column('verify_ssl', sa.Boolean(), nullable=False, server_default='false')
    )

    # Remove server_default after adding the column (best practice)
    op.alter_column('proxmox_clusters', 'verify_ssl', server_default=None)


def downgrade() -> None:
    """Remove verify_ssl column from proxmox_clusters table."""
    op.drop_column('proxmox_clusters', 'verify_ssl')
