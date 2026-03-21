"""
Background tasks for VM provisioning and management.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.virtual_machine import VirtualMachine
from app.models.vm_disk import VMDisk
from app.models.iso_image import ISOImage
from app.models.proxmox_cluster import ProxmoxCluster
from app.models.vpc_network import VPCNetwork
from app.models.vm_network_interface import VMNetworkInterface
from app.services.proxmox_service import ProxmoxService
from app.services.quota_service import QuotaService

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""

    _db: Optional[Session] = None

    @property
    def db(self) -> Session:
        """Get database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Close database session after task completes."""
        if self._db is not None:
            self._db.close()
            self._db = None


def map_ostype_to_proxmox(ostype: Optional[str]) -> str:
    """Map user-friendly OS type to Proxmox ostype codes."""
    ostype_map = {
        "linux": "l26",
        "ubuntu": "l26",
        "debian": "l26",
        "centos": "l26",
        "rhel": "l26",
        "fedora": "l26",
        "rocky": "l26",
        "alma": "l26",
        "windows": "win11",
        "windows-11": "win11",
        "windows-10": "win10",
        "windows-8": "win8",
        "windows-7": "win7",
        "windows-vista": "wvista",
        "windows-2008": "w2k8",
        "windows-2003": "w2k3",
        "windows-2000": "w2k",
        "windows-xp": "wxp",
        "solaris": "solaris",
        "other": "other",
    }

    if not ostype:
        return "l26"

    return ostype_map.get(ostype.lower(), "l26")


@celery_app.task(bind=True, base=DatabaseTask, max_retries=3, default_retry_delay=60)
def provision_vm_with_disks(self, vm_id: str):
    """
    Provision a VM with multiple disks and optional ISO boot on Proxmox.

    This task:
    1. Gets VM and disk records from database
    2. Creates base VM on Proxmox (without disks)
    3. Adds each disk one by one
    4. Mounts ISO if specified
    5. Sets boot order
    6. Updates VM and disk statuses

    Args:
        vm_id: Virtual machine UUID

    Raises:
        Exception: If provisioning fails after max retries
    """
    db = self.db

    try:
        # Get VM record
        result = db.execute(
            select(VirtualMachine).where(
                VirtualMachine.id == vm_id,
                VirtualMachine.deleted_at.is_(None)
            )
        )
        vm = result.scalar_one_or_none()

        if not vm:
            logger.error(f"VM {vm_id} not found")
            return {"status": "error", "message": "VM not found"}

        if vm.status not in ["provisioning", "error"]:
            logger.info(f"VM {vm_id} already provisioned (status: {vm.status})")
            return {"status": "success", "message": "VM already provisioned"}

        # Get disks for this VM
        result = db.execute(
            select(VMDisk).where(
                VMDisk.vm_id == vm_id,
                VMDisk.deleted_at.is_(None)
            ).order_by(VMDisk.disk_index)
        )
        disks = list(result.scalars().all())

        logger.info(f"Provisioning VM {vm_id} with {len(disks)} disk(s)")

        # Get Proxmox cluster
        result = db.execute(
            select(ProxmoxCluster).where(
                ProxmoxCluster.id == vm.proxmox_cluster_id
            )
        )
        cluster = result.scalar_one_or_none()

        if not cluster:
            raise Exception(f"Proxmox cluster {vm.proxmox_cluster_id} not found")

        proxmox = ProxmoxService(cluster=cluster)

        # Map OS type
        proxmox_ostype = map_ostype_to_proxmox(vm.os_type)

        # Get VPC network if specified
        network = None
        if vm.network_id:
            result = db.execute(
                select(VPCNetwork).where(
                    VPCNetwork.id == vm.network_id,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
            network = result.scalar_one_or_none()
            if network:
                logger.info(f"VM {vm_id} will use network {network.name} (VLAN {network.vlan_id})")

        try:
            # Step 1: Create base VM without disks
            logger.info(f"Creating base VM {vm.proxmox_vmid} on node {vm.proxmox_node}")

            # Build network configuration
            create_vm_kwargs = {
                "sockets": vm.cpu_sockets,
                "ostype": proxmox_ostype
            }

            if network:
                # Build VLAN-tagged network config
                net0_config = proxmox.build_network_config(
                    interface_name="net0",
                    vlan_id=network.vlan_id,
                    bridge=network.bridge,
                    model="virtio"
                )
                create_vm_kwargs["net0"] = net0_config
                logger.info(f"Network config for VM {vm_id}: {net0_config}")
            # else: uses default "virtio,bridge=vmbr0" from create_vm_base

            result = proxmox.create_vm_base(
                node=vm.proxmox_node,
                vmid=vm.proxmox_vmid,
                name=vm.name,
                cores=vm.cpu_cores,
                memory=vm.memory_mb,
                **create_vm_kwargs
            )

            logger.info(f"Base VM created: {result}")

            # Step 2: Add each disk
            boot_devices = []
            cdrom_device = None

            for disk in disks:
                try:
                    if disk.is_cdrom:
                        # Handle CD-ROM with ISO
                        if disk.iso_image_id:
                            result = db.execute(
                                select(ISOImage).where(ISOImage.id == disk.iso_image_id)
                            )
                            iso = result.scalar_one_or_none()

                            if iso and iso.proxmox_volid:
                                logger.info(f"Mounting ISO {iso.proxmox_volid} as {disk.disk_interface}{disk.disk_number}")

                                proxmox.mount_iso_to_vm(
                                    node=vm.proxmox_node,
                                    vmid=vm.proxmox_vmid,
                                    iso_volid=iso.proxmox_volid,
                                    disk_interface=disk.disk_interface,
                                    disk_number=disk.disk_number
                                )

                                cdrom_device = f"{disk.disk_interface}{disk.disk_number}"
                                disk.status = "ready"
                                disk.attached_at = datetime.utcnow()
                                disk.proxmox_disk_id = cdrom_device

                    else:
                        # Handle regular disk
                        logger.info(f"Adding disk {disk.disk_interface}{disk.disk_number}: {disk.size_gb}GB on {disk.storage_pool}")

                        result = proxmox.add_disk_to_vm(
                            node=vm.proxmox_node,
                            vmid=vm.proxmox_vmid,
                            disk_interface=disk.disk_interface,
                            disk_number=disk.disk_number,
                            storage=disk.storage_pool,
                            size_gb=disk.size_gb,
                            disk_format=disk.disk_format
                        )

                        disk_id = f"{disk.disk_interface}{disk.disk_number}"
                        disk.status = "ready"
                        disk.attached_at = datetime.utcnow()
                        disk.proxmox_disk_id = disk_id

                        # Track boot disk
                        if disk.is_boot_disk:
                            boot_devices.insert(0, disk_id)  # Boot disk first
                        else:
                            boot_devices.append(disk_id)

                    db.commit()

                except Exception as disk_error:
                    logger.error(f"Failed to attach disk {disk.id}: {disk_error}")
                    disk.status = "error"
                    db.commit()
                    raise

            # Step 3: Set boot order
            if boot_devices or cdrom_device:
                boot_order = []

                # If there's a CD-ROM, boot from it first (for OS installation)
                if cdrom_device:
                    boot_order.append(cdrom_device)

                # Then boot from disk
                boot_order.extend(boot_devices)

                if boot_order:
                    logger.info(f"Setting boot order: {boot_order}")
                    proxmox.set_boot_order(
                        node=vm.proxmox_node,
                        vmid=vm.proxmox_vmid,
                        boot_order=boot_order
                    )

                    vm.boot_order = ";".join(boot_order)

            # Step 4: Create network interface record if network was attached
            if network:
                network_interface = VMNetworkInterface(
                    vm_id=vm.id,
                    network_id=network.id,
                    interface_name="net0",
                    model="virtio",
                    is_primary=True,
                    interface_order=0,
                    proxmox_config=create_vm_kwargs.get("net0", "")
                )
                db.add(network_interface)
                logger.info(f"Created network interface record for VM {vm_id}")

            # Step 5: Update VM status
            vm.status = "stopped"  # Ready but not started
            vm.provisioned_at = datetime.utcnow()
            db.commit()

            logger.info(f"VM {vm_id} successfully provisioned on Proxmox")

            return {
                "status": "success",
                "vm_id": vm_id,
                "proxmox_vmid": vm.proxmox_vmid,
                "disks_attached": len([d for d in disks if d.status == "ready"])
            }

        except Exception as proxmox_error:
            logger.error(f"Proxmox provisioning failed for VM {vm_id}: {proxmox_error}")

            # Try to clean up VM from Proxmox if it was partially created
            try:
                proxmox.delete_vm(vm.proxmox_node, vm.proxmox_vmid)
                logger.info(f"Cleaned up partially created VM {vm.proxmox_vmid}")
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup VM {vm.proxmox_vmid}: {cleanup_error}")

            raise proxmox_error

    except Exception as e:
        logger.error(f"Error provisioning VM {vm_id}: {e}")

        # Update VM status to error
        try:
            vm.status = "error"
            db.commit()
        except:
            pass

        # Release quota on failure
        try:
            # Calculate total storage from disks
            total_storage_gb = sum(disk.size_gb for disk in disks if not disk.is_cdrom)

            quota_service = QuotaService(db)
            quota_service.decrement_usage(
                organization_id=vm.organization_id,
                cpu_cores=vm.cpu_cores,
                memory_gb=vm.memory_mb / 1024,
                storage_gb=total_storage_gb,
                vm_count=1
            )
            db.commit()
            logger.info(f"Released quota for failed VM {vm_id}")
        except Exception as quota_error:
            logger.error(f"Failed to release quota for VM {vm_id}: {quota_error}")

        # Retry if not at max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying VM provisioning {vm_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)

        return {"status": "error", "message": str(e)}
