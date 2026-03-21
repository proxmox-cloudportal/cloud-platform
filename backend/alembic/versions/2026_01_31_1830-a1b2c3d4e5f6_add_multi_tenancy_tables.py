"""Add multi-tenancy tables

Revision ID: a1b2c3d4e5f6
Revises: dff514f1022e
Create Date: 2026-01-31 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'dff514f1022e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create organization_members and resource_quotas tables, add org fields to proxmox_clusters."""
    
    # Drop organization_members table
    #op.drop_index('idx_org_members_org_role', table_name='organization_members')
    #op.drop_index('idx_org_members_org_id', table_name='organization_members')
    #op.drop_index('idx_org_members_user_id', table_name='organization_members')
    op.drop_table('organization_members')
    op.drop_table('resource_quotas')

    # Create organization_members table
    op.create_table(
        'organization_members',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='member'),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('invited_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('user_id', 'organization_id', name='uq_user_org'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )

    # Create indexes for organization_members
    op.create_index('idx_org_members_user_id', 'organization_members', ['user_id'])
    op.create_index('idx_org_members_org_id', 'organization_members', ['organization_id'])
    op.create_index('idx_org_members_org_role', 'organization_members', ['organization_id', 'role'])

    # Create resource_quotas table
    op.create_table(
        'resource_quotas',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('limit_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('used_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('last_calculated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('organization_id', 'resource_type', name='uq_org_resource'),
        sa.CheckConstraint('limit_value >= 0', name='check_positive_limit'),
        sa.CheckConstraint('used_value >= 0', name='check_positive_usage'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )

    # Create indexes for resource_quotas
    op.create_index('idx_quotas_org_id', 'resource_quotas', ['organization_id'])
    op.create_index('idx_quotas_org_resource', 'resource_quotas', ['organization_id', 'resource_type'])

    # Add organization fields to proxmox_clusters
    op.add_column('proxmox_clusters', sa.Column('organization_id', sa.String(length=36), nullable=True))
    op.add_column('proxmox_clusters', sa.Column('is_shared', sa.Boolean(), nullable=False, server_default='0'))
    op.create_foreign_key('fk_proxmox_clusters_organization', 'proxmox_clusters', 'organizations', ['organization_id'], ['id'], ondelete='SET NULL')
    op.create_index('idx_clusters_org_id', 'proxmox_clusters', ['organization_id'])


def downgrade() -> None:
    """Drop multi-tenancy tables and remove org fields from proxmox_clusters."""

    # Remove organization fields from proxmox_clusters
    op.drop_index('idx_clusters_org_id', table_name='proxmox_clusters')
    op.drop_constraint('fk_proxmox_clusters_organization', 'proxmox_clusters', type_='foreignkey')
    op.drop_column('proxmox_clusters', 'is_shared')
    op.drop_column('proxmox_clusters', 'organization_id')

    # Drop resource_quotas table
    op.drop_index('idx_quotas_org_resource', table_name='resource_quotas')
    op.drop_index('idx_quotas_org_id', table_name='resource_quotas')
    op.drop_table('resource_quotas')

    # Drop organization_members table
    op.drop_index('idx_org_members_org_role', table_name='organization_members')
    op.drop_index('idx_org_members_org_id', table_name='organization_members')
    op.drop_index('idx_org_members_user_id', table_name='organization_members')
    op.drop_table('organization_members')
