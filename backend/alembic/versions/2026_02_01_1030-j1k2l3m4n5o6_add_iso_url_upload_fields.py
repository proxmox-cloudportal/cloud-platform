"""add iso url upload fields

Revision ID: j1k2l3m4n5o6
Revises: f6g7h8i9j0k1
Create Date: 2026-02-01 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'j1k2l3m4n5o6'
down_revision: Union[str, None] = 'f6g7h8i9j0k1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add URL upload support fields to iso_images table."""

    # Add source URL field
    op.add_column('iso_images', sa.Column('source_url', sa.Text(), nullable=True))

    # Add source type field (upload or url)
    op.add_column('iso_images', sa.Column('source_type', sa.String(20), nullable=False, server_default='upload'))

    # Add download status for URL downloads
    op.add_column('iso_images', sa.Column('download_status', sa.String(50), nullable=True))

    # Add index for source_url
    op.create_index('idx_iso_source_url', 'iso_images', ['source_url'])


def downgrade() -> None:
    """Remove URL upload support fields from iso_images table."""

    # Drop index
    op.drop_index('idx_iso_source_url', table_name='iso_images')

    # Drop columns
    op.drop_column('iso_images', 'download_status')
    op.drop_column('iso_images', 'source_type')
    op.drop_column('iso_images', 'source_url')
