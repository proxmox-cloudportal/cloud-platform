"""add iso disk storage tables

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-02-01 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e5f6g7h8i9j0'
down_revision: Union[str, None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create iso_images, vm_disks, and storage_pools tables."""
    
    # Create iso_images table
    op.create_table(
        'iso_images',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        # Ownership
        sa.Column('organization_id', sa.String(36), nullable=True),
        sa.Column('uploaded_by', sa.String(36), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),

        # ISO Metadata
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('os_type', sa.String(50), nullable=True),
        sa.Column('os_version', sa.String(100), nullable=True),
        sa.Column('architecture', sa.String(20), nullable=False, server_default='x86_64'),

        # File Information
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('checksum_sha256', sa.String(64), nullable=False),

        # Storage Location
        sa.Column('storage_backend', sa.String(50), nullable=False, server_default='local'),
        sa.Column('local_path', sa.Text(), nullable=True),
        sa.Column('proxmox_cluster_id', sa.String(36), nullable=True),
        sa.Column('proxmox_storage', sa.String(100), nullable=True),
        sa.Column('proxmox_volid', sa.String(255), nullable=True),

        # Upload Status
        sa.Column('upload_status', sa.String(50), nullable=False, server_default='uploading'),
        sa.Column('upload_progress', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('synced_to_proxmox_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['proxmox_cluster_id'], ['proxmox_clusters.id'], ondelete='SET NULL'),
    )

    # Create indexes for iso_images
    op.create_index('idx_iso_org', 'iso_images', ['organization_id'])
    op.create_index('idx_iso_uploader', 'iso_images', ['uploaded_by'])
    op.create_index('idx_iso_status', 'iso_images', ['upload_status'])
    op.create_index('idx_iso_checksum', 'iso_images', ['checksum_sha256'], unique=True)

    # Create vm_disks table
    op.create_table(
        'vm_disks',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        # VM Association
        sa.Column('vm_id', sa.String(36), nullable=False),

        # Disk Configuration
        sa.Column('disk_index', sa.Integer(), nullable=False),
        sa.Column('disk_interface', sa.String(20), nullable=False),
        sa.Column('disk_number', sa.Integer(), nullable=False),

        # Storage
        sa.Column('storage_pool', sa.String(100), nullable=False),
        sa.Column('size_gb', sa.Integer(), nullable=False),
        sa.Column('disk_format', sa.String(20), nullable=True),

        # Disk Type
        sa.Column('is_boot_disk', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_cdrom', sa.Boolean(), nullable=False, server_default='false'),

        # ISO Mount
        sa.Column('iso_image_id', sa.String(36), nullable=True),

        # Proxmox Details
        sa.Column('proxmox_disk_id', sa.String(255), nullable=True),

        # Status
        sa.Column('status', sa.String(50), nullable=False, server_default='creating'),

        # Timestamps
        sa.Column('attached_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['vm_id'], ['virtual_machines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['iso_image_id'], ['iso_images.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('vm_id', 'disk_interface', 'disk_number', name='uq_vm_disk_interface'),
    )

    # Create indexes for vm_disks
    op.create_index('idx_disk_vm', 'vm_disks', ['vm_id'])
    op.create_index('idx_disk_iso', 'vm_disks', ['iso_image_id'])

    # Create storage_pools table
    op.create_table(
        'storage_pools',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        # Proxmox Association
        sa.Column('proxmox_cluster_id', sa.String(36), nullable=False),
        sa.Column('storage_name', sa.String(100), nullable=False),
        sa.Column('storage_type', sa.String(50), nullable=False),

        # Capabilities - Use JSONB for PostgreSQL
        sa.Column('content_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),

        # Capacity
        sa.Column('total_bytes', sa.BigInteger(), nullable=True),
        sa.Column('used_bytes', sa.BigInteger(), nullable=True),
        sa.Column('available_bytes', sa.BigInteger(), nullable=True),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default='false'),

        # Sync
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['proxmox_cluster_id'], ['proxmox_clusters.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('proxmox_cluster_id', 'storage_name', name='uq_cluster_storage'),
    )

    # Create indexes for storage_pools
    op.create_index('idx_pool_cluster', 'storage_pools', ['proxmox_cluster_id'])

    # Add boot_order column to virtual_machines
    op.add_column('virtual_machines', sa.Column('boot_order', sa.String(100), nullable=True))


def downgrade() -> None:
    """Drop iso_images, vm_disks, and storage_pools tables."""

    # Remove boot_order from virtual_machines
    op.drop_column('virtual_machines', 'boot_order')

    # Drop storage_pools
    op.drop_index('idx_pool_cluster', table_name='storage_pools')
    op.drop_table('storage_pools')

    # Drop vm_disks
    op.drop_index('idx_disk_iso', table_name='vm_disks')
    op.drop_index('idx_disk_vm', table_name='vm_disks')
    op.drop_table('vm_disks')

    # Drop iso_images
    op.drop_index('idx_iso_checksum', table_name='iso_images')
    op.drop_index('idx_iso_status', table_name='iso_images')
    op.drop_index('idx_iso_uploader', table_name='iso_images')
    op.drop_index('idx_iso_org', table_name='iso_images')
    op.drop_table('iso_images')
