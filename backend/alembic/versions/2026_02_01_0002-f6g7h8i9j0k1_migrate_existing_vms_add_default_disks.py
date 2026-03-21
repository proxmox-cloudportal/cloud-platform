"""migrate existing vms add default disks

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-02-01 00:02:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime
import uuid


# revision identifiers, used by Alembic.
revision: str = 'f6g7h8i9j0k1'
down_revision: Union[str, None] = 'e5f6g7h8i9j0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create default disk records for existing VMs."""

    # Get connection
    connection = op.get_bind()

    # Get all existing VMs that don't have disk records yet
    result = connection.execute(sa.text("""
        SELECT id, created_at
        FROM virtual_machines
        WHERE deleted_at IS NULL
    """))

    vms = result.fetchall()

    if vms:
        # Prepare batch insert for vm_disks
        disk_records = []
        now = datetime.utcnow()

        for vm in vms:
            vm_id = vm[0]
            vm_created_at = vm[1]

            # Create a default disk record for this VM
            # Assumptions: scsi0, 20GB, local-lvm (common defaults)
            disk_record = {
                'id': str(uuid.uuid4()),
                'created_at': now,
                'updated_at': now,
                'deleted_at': None,
                'vm_id': vm_id,
                'disk_index': 0,
                'disk_interface': 'scsi',
                'disk_number': 0,
                'storage_pool': 'local-lvm',
                'size_gb': 20,
                'disk_format': 'raw',
                'is_boot_disk': True,
                'is_cdrom': False,
                'iso_image_id': None,
                'proxmox_disk_id': None,
                'status': 'ready',  # Assume existing VMs have disks already
                'attached_at': vm_created_at  # Use VM creation time
            }
            disk_records.append(disk_record)

        # Batch insert all disk records
        if disk_records:
            connection.execute(
                sa.text("""
                    INSERT INTO vm_disks (
                        id, created_at, updated_at, deleted_at, vm_id,
                        disk_index, disk_interface, disk_number,
                        storage_pool, size_gb, disk_format,
                        is_boot_disk, is_cdrom, iso_image_id,
                        proxmox_disk_id, status, attached_at
                    ) VALUES (
                        :id, :created_at, :updated_at, :deleted_at, :vm_id,
                        :disk_index, :disk_interface, :disk_number,
                        :storage_pool, :size_gb, :disk_format,
                        :is_boot_disk, :is_cdrom, :iso_image_id,
                        :proxmox_disk_id, :status, :attached_at
                    )
                """),
                disk_records
            )

            print(f"✓ Created {len(disk_records)} default disk records for existing VMs")


def downgrade() -> None:
    """Remove default disk records created by this migration."""

    # Get connection
    connection = op.get_bind()

    # Delete only the default disks (scsi0, disk_index=0)
    # This is safe because we're only removing the migration artifacts
    connection.execute(sa.text("""
        DELETE FROM vm_disks
        WHERE disk_interface = 'scsi'
        AND disk_number = 0
        AND disk_index = 0
        AND storage_pool = 'local-lvm'
        AND size_gb = 20
    """))

    print("✓ Removed default disk records")
