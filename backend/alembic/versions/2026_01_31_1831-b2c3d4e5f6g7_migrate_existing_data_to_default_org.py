"""Migrate existing data to default organization

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-31 18:31:00.000000

"""
from typing import Sequence, Union
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default quota limits
DEFAULT_QUOTAS = {
    "cpu_cores": 100.0,
    "memory_gb": 512.0,
    "storage_gb": 5000.0,
    "vm_count": 50.0,
    "cluster_count": 5.0
}


def upgrade() -> None:
    """Migrate existing VMs and users to default organization."""

    conn = op.get_bind()

    # 1. Create "Default Organization" if it doesn't exist
    default_org_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Check if default org already exists
    result = conn.execute(
        sa.text("SELECT id FROM organizations WHERE slug = 'default' LIMIT 1")
    )
    existing_org = result.fetchone()

    if existing_org:
        default_org_id = existing_org[0]
        print(f"Using existing default organization: {default_org_id}")
    else:
        # Create default organization
        conn.execute(
            sa.text("""
                INSERT INTO organizations (id, name, slug, description, created_at, updated_at, is_active)
                VALUES (:id, :name, :slug, :description, :created_at, :updated_at, true)
            """),
            {
                "id": default_org_id,
                "name": "Default Organization",
                "slug": "default",
                "description": "Default organization for migrated resources",
                "created_at": now,
                "updated_at": now
            }
        )
        print(f"Created default organization: {default_org_id}")

    # 2. Assign all existing VMs to default organization
    result = conn.execute(
        sa.text("UPDATE virtual_machines SET organization_id = :org_id WHERE organization_id IS NULL"),
        {"org_id": default_org_id}
    )
    vm_count = result.rowcount
    print(f"Assigned {vm_count} VMs to default organization")

    # 3. Create organization memberships for all VM owners as admins
    # Get distinct VM owners
    result = conn.execute(
        sa.text("""
            SELECT DISTINCT owner_id
            FROM virtual_machines
            WHERE owner_id IS NOT NULL
            AND deleted_at IS NULL
        """)
    )
    vm_owners = [row[0] for row in result.fetchall()]

    # For each owner, create membership if not exists
    membership_count = 0
    for owner_id in vm_owners:
        # Check if membership already exists
        result = conn.execute(
            sa.text("""
                SELECT id FROM organization_members
                WHERE user_id = :user_id AND organization_id = :org_id
                LIMIT 1
            """),
            {"user_id": owner_id, "org_id": default_org_id}
        )

        if not result.fetchone():
            member_id = str(uuid.uuid4())
            conn.execute(
                sa.text("""
                    INSERT INTO organization_members
                    (id, user_id, organization_id, role, joined_at, created_at, updated_at)
                    VALUES (:id, :user_id, :org_id, :role, :joined_at, :created_at, :updated_at)
                """),
                {
                    "id": member_id,
                    "user_id": owner_id,
                    "org_id": default_org_id,
                    "role": "admin",
                    "joined_at": now,
                    "created_at": now,
                    "updated_at": now
                }
            )
            membership_count += 1

    print(f"Created {membership_count} organization memberships for VM owners")

    # 4. Mark all existing Proxmox clusters as shared
    result = conn.execute(
        sa.text("UPDATE proxmox_clusters SET is_shared = true WHERE is_shared = false OR is_shared IS NULL")
    )
    cluster_count = result.rowcount
    print(f"Marked {cluster_count} clusters as shared")

    # 5. Create default quotas for the default organization
    quota_count = 0
    for resource_type, limit_value in DEFAULT_QUOTAS.items():
        # Check if quota already exists
        result = conn.execute(
            sa.text("""
                SELECT id FROM resource_quotas
                WHERE organization_id = :org_id AND resource_type = :resource_type
                LIMIT 1
            """),
            {"org_id": default_org_id, "resource_type": resource_type}
        )

        if not result.fetchone():
            quota_id = str(uuid.uuid4())
            conn.execute(
                sa.text("""
                    INSERT INTO resource_quotas
                    (id, organization_id, resource_type, limit_value, used_value, created_at, updated_at)
                    VALUES (:id, :org_id, :resource_type, :limit_value, :used_value, :created_at, :updated_at)
                """),
                {
                    "id": quota_id,
                    "org_id": default_org_id,
                    "resource_type": resource_type,
                    "limit_value": limit_value,
                    "used_value": 0.0,
                    "created_at": now,
                    "updated_at": now
                }
            )
            quota_count += 1

    print(f"Created {quota_count} default quotas")

    # 6. Calculate initial quota usage from existing VMs
    # result = conn.execute(
    #     sa.text("""
    #         SELECT
    #             SUM(cpu_cores) as total_cpu,
    #             SUM(memory_mb / 1024.0) as total_memory_gb,
    #             SUM(disk_gb) as total_storage_gb,
    #             COUNT(*) as total_vms
    #         FROM virtual_machines
    #         WHERE organization_id = :org_id
    #         AND deleted_at IS NULL
    #     """),
    #     {"org_id": default_org_id}
    # )

    # usage = result.fetchone()
    # if usage:
    #     total_cpu = usage[0] or 0
    #     total_memory_gb = usage[1] or 0
    #     total_storage_gb = usage[2] or 0
    #     total_vms = usage[3] or 0

    #     # Update quota usage
    #     conn.execute(
    #         sa.text("""
    #             UPDATE resource_quotas
    #             SET used_value = :used_value, last_calculated_at = :calculated_at
    #             WHERE organization_id = :org_id AND resource_type = :resource_type
    #         """),
    #         [
    #             {"org_id": default_org_id, "resource_type": "cpu_cores", "used_value": float(total_cpu), "calculated_at": now},
    #             {"org_id": default_org_id, "resource_type": "memory_gb", "used_value": float(total_memory_gb), "calculated_at": now},
    #             {"org_id": default_org_id, "resource_type": "storage_gb", "used_value": float(total_storage_gb), "calculated_at": now},
    #             {"org_id": default_org_id, "resource_type": "vm_count", "used_value": float(total_vms), "calculated_at": now},
    #         ]
    #     )

    #     # Get cluster count
    #     result = conn.execute(
    #         sa.text("""
    #             SELECT COUNT(*) FROM proxmox_clusters
    #             WHERE organization_id = :org_id AND deleted_at IS NULL
    #         """),
    #         {"org_id": default_org_id}
    #     )
    #     cluster_count = result.scalar() or 0

    #     conn.execute(
    #         sa.text("""
    #             UPDATE resource_quotas
    #             SET used_value = :used_value, last_calculated_at = :calculated_at
    #             WHERE organization_id = :org_id AND resource_type = 'cluster_count'
    #         """),
    #         {"org_id": default_org_id, "used_value": float(cluster_count), "calculated_at": now}
    #     )

    #print(f"Calculated quota usage - CPU: {total_cpu}, Memory: {total_memory_gb}GB, Storage: {total_storage_gb}GB, VMs: {total_vms}, Clusters: {cluster_count}")


def downgrade() -> None:
    """Revert data migration."""

    conn = op.get_bind()

    # Find default organization
    result = conn.execute(
        sa.text("SELECT id FROM organizations WHERE slug = 'default' LIMIT 1")
    )
    default_org = result.fetchone()

    if default_org:
        default_org_id = default_org[0]

        # Remove organization from VMs
        conn.execute(
            sa.text("UPDATE virtual_machines SET organization_id = NULL WHERE organization_id = :org_id"),
            {"org_id": default_org_id}
        )

        # Remove organization memberships
        conn.execute(
            sa.text("DELETE FROM organization_members WHERE organization_id = :org_id"),
            {"org_id": default_org_id}
        )

        # Remove quotas
        conn.execute(
            sa.text("DELETE FROM resource_quotas WHERE organization_id = :org_id"),
            {"org_id": default_org_id}
        )

        # Delete default organization
        conn.execute(
            sa.text("DELETE FROM organizations WHERE id = :org_id"),
            {"org_id": default_org_id}
        )

        print(f"Removed default organization and associated data")

    # Unmark clusters as shared
    conn.execute(
        sa.text("UPDATE proxmox_clusters SET is_shared = 0, organization_id = NULL")
    )
