"""phase 3 vpc networking

Revision ID: p3v1n2e3t4w5
Revises: j1k2l3m4n5o6
Create Date: 2026-02-02 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'p3v1n2e3t4w5'
down_revision: Union[str, None] = 'j1k2l3m4n5o6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create VPC networking tables with VLAN isolation."""

    # 1. Create vpc_networks table
    op.create_table(
        'vpc_networks',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        # Ownership
        sa.Column('organization_id', sa.String(36), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=False),

        # Network configuration
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # VLAN configuration
        sa.Column('vlan_id', sa.Integer(), nullable=False),
        sa.Column('bridge', sa.String(50), nullable=False, server_default='vmbr0'),

        # Subnet configuration
        sa.Column('cidr', sa.String(50), nullable=False),
        sa.Column('gateway', sa.String(45), nullable=True),
        sa.Column('dns_servers', sa.JSON(), nullable=True),

        # Settings
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tags', sa.JSON(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_networks_org_id', 'vpc_networks', ['organization_id'])
    op.create_index('idx_networks_vlan_id', 'vpc_networks', ['vlan_id'])
    op.create_index('idx_networks_name', 'vpc_networks', ['name'])
    op.create_index('idx_networks_unique_vlan', 'vpc_networks', ['vlan_id'], unique=True)

    # 2. Create vlan_pool table
    op.create_table(
        'vlan_pool',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        sa.Column('vlan_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='available'),
        sa.Column('allocated_to_network_id', sa.String(36), nullable=True),
        sa.Column('allocated_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['allocated_to_network_id'], ['vpc_networks.id'], ondelete='SET NULL'),
        sa.CheckConstraint('vlan_id >= 1 AND vlan_id <= 4094', name='check_vlan_range'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_vlan_pool_status', 'vlan_pool', ['status'])
    op.create_index('idx_vlan_pool_vlan_id', 'vlan_pool', ['vlan_id'])
    op.create_index('idx_vlan_pool_unique_vlan', 'vlan_pool', ['vlan_id'], unique=True)

    # 3. Create network_ip_pools table
    op.create_table(
        'network_ip_pools',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        sa.Column('network_id', sa.String(36), nullable=False),
        sa.Column('pool_name', sa.String(255), nullable=False),
        sa.Column('start_ip', sa.String(45), nullable=False),
        sa.Column('end_ip', sa.String(45), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['network_id'], ['vpc_networks.id'], ondelete='CASCADE'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_ip_pools_network_id', 'network_ip_pools', ['network_id'])

    # 4. Create network_ip_allocations table
    op.create_table(
        'network_ip_allocations',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        sa.Column('network_id', sa.String(36), nullable=False),
        sa.Column('ip_pool_id', sa.String(36), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=False),

        # Assignment
        sa.Column('vm_id', sa.String(36), nullable=True),
        sa.Column('interface_name', sa.String(10), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='allocated'),

        # Metadata
        sa.Column('hostname', sa.String(255), nullable=True),
        sa.Column('mac_address', sa.String(17), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['network_id'], ['vpc_networks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ip_pool_id'], ['network_ip_pools.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vm_id'], ['virtual_machines.id'], ondelete='SET NULL'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_ip_alloc_network', 'network_ip_allocations', ['network_id'])
    op.create_index('idx_ip_alloc_vm', 'network_ip_allocations', ['vm_id'])
    op.create_index('idx_ip_alloc_status', 'network_ip_allocations', ['status'])

    # 5. Create vm_network_interfaces table
    op.create_table(
        'vm_network_interfaces',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        sa.Column('vm_id', sa.String(36), nullable=False),
        sa.Column('network_id', sa.String(36), nullable=False),

        sa.Column('interface_name', sa.String(10), nullable=False),
        sa.Column('mac_address', sa.String(17), nullable=True),
        sa.Column('model', sa.String(20), nullable=False, server_default='virtio'),

        sa.Column('ip_allocation_id', sa.String(36), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('interface_order', sa.Integer(), nullable=False),

        sa.Column('proxmox_config', sa.Text(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['vm_id'], ['virtual_machines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['network_id'], ['vpc_networks.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['ip_allocation_id'], ['network_ip_allocations.id'], ondelete='SET NULL'),
        sa.CheckConstraint('interface_order >= 0 AND interface_order <= 3', name='check_interface_order'),
        sa.CheckConstraint("interface_name IN ('net0', 'net1', 'net2', 'net3')", name='check_interface_name'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index('idx_vm_interfaces_vm', 'vm_network_interfaces', ['vm_id'])
    op.create_index('idx_vm_interfaces_network', 'vm_network_interfaces', ['network_id'])
    op.create_index('idx_vm_interfaces_order', 'vm_network_interfaces', ['vm_id', 'interface_order'])

    # 6. Update proxmox_clusters table
    op.add_column('proxmox_clusters', sa.Column('default_bridge', sa.String(50), nullable=False, server_default='vmbr0'))
    op.add_column('proxmox_clusters', sa.Column('supported_bridges', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop VPC networking tables."""

    # Remove columns from proxmox_clusters
    op.drop_column('proxmox_clusters', 'supported_bridges')
    op.drop_column('proxmox_clusters', 'default_bridge')

    # Drop tables in reverse order
    op.drop_index('idx_vm_interfaces_order', table_name='vm_network_interfaces')
    op.drop_index('idx_vm_interfaces_network', table_name='vm_network_interfaces')
    op.drop_index('idx_vm_interfaces_vm', table_name='vm_network_interfaces')
    op.drop_table('vm_network_interfaces')

    op.drop_index('idx_ip_alloc_status', table_name='network_ip_allocations')
    op.drop_index('idx_ip_alloc_vm', table_name='network_ip_allocations')
    op.drop_index('idx_ip_alloc_network', table_name='network_ip_allocations')
    op.drop_table('network_ip_allocations')

    op.drop_index('idx_ip_pools_network_id', table_name='network_ip_pools')
    op.drop_table('network_ip_pools')

    op.drop_index('idx_vlan_pool_unique_vlan', table_name='vlan_pool')
    op.drop_index('idx_vlan_pool_vlan_id', table_name='vlan_pool')
    op.drop_index('idx_vlan_pool_status', table_name='vlan_pool')
    op.drop_table('vlan_pool')

    op.drop_index('idx_networks_unique_vlan', table_name='vpc_networks')
    op.drop_index('idx_networks_name', table_name='vpc_networks')
    op.drop_index('idx_networks_vlan_id', table_name='vpc_networks')
    op.drop_index('idx_networks_org_id', table_name='vpc_networks')
    op.drop_table('vpc_networks')
