"""
VM Disk management endpoints for attaching, detaching, and managing disks.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.virtual_machine import VirtualMachine
from app.models.vm_disk import VMDisk
from app.models.iso_image import ISOImage
from app.schemas.vm_disk import (
    DiskAttach,
    DiskResize,
    DiskAttachISO,
    DiskResponse,
    DiskListResponse,
)
from app.core.deps import get_current_user, OrgContext, RequirePermission
from app.core.rbac import Role, Permission
from app.models.user import User
from app.services.proxmox_service import ProxmoxService

router = APIRouter(prefix="/vms", tags=["VM Disks"])


@router.get("/{vm_id}/disks", response_model=DiskListResponse)
async def list_vm_disks(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    List all disks attached to a VM.

    **Permissions Required:** VM_READ
    """
    # Verify VM access
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only see their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Get disks
    result = await db.execute(
        select(VMDisk).where(
            VMDisk.vm_id == vm_id,
            VMDisk.deleted_at.is_(None)
        ).order_by(VMDisk.disk_index)
    )
    disks = list(result.scalars().all())

    return DiskListResponse(
        data=disks,
        total=len(disks)
    )


@router.post("/{vm_id}/disks", response_model=DiskResponse, status_code=status.HTTP_202_ACCEPTED)
async def attach_disk_to_vm(
    vm_id: str,
    disk_data: DiskAttach,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Attach a new disk to an existing VM.

    The disk will be created and attached asynchronously on Proxmox.

    **Permissions Required:** VM_UPDATE
    """
    # Verify VM access
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only modify their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Check quota for additional storage
    from app.services.quota_service import QuotaService

    quota_service = QuotaService(db)
    quota_check = await quota_service.check_quota_availability(
        organization_id=org_context.org_id,
        storage_gb=disk_data.size_gb
    )

    if not quota_check.is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quota exceeded: {', '.join(quota_check.exceeded_resources)}"
        )

    # Get next available disk index (check all disks including soft-deleted)
    result = await db.execute(
        select(VMDisk).where(
            VMDisk.vm_id == vm_id
            # NOTE: Not filtering by deleted_at to avoid number conflicts
        ).order_by(VMDisk.disk_index.desc()).limit(1)
    )
    last_disk = result.scalar_one_or_none()
    next_index = (last_disk.disk_index + 1) if last_disk else 0

    # Determine disk number for the interface (check all disks including soft-deleted)
    result = await db.execute(
        select(VMDisk).where(
            VMDisk.vm_id == vm_id,
            VMDisk.disk_interface == disk_data.disk_interface
            # NOTE: Not filtering by deleted_at to avoid number conflicts
        ).order_by(VMDisk.disk_number.desc()).limit(1)
    )
    last_interface_disk = result.scalar_one_or_none()
    next_disk_number = (last_interface_disk.disk_number + 1) if last_interface_disk else 0

    # Create disk record
    disk = VMDisk(
        vm_id=vm_id,
        disk_index=next_index,
        disk_interface=disk_data.disk_interface,
        disk_number=next_disk_number,
        storage_pool=disk_data.storage_pool,
        size_gb=disk_data.size_gb,
        disk_format=disk_data.disk_format,
        is_boot_disk=False,
        is_cdrom=False,
        status="creating"
    )

    db.add(disk)
    await db.commit()
    await db.refresh(disk)

    # Attach disk to VM on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)

        proxmox_service.add_disk_to_vm(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            disk_interface=disk.disk_interface,
            disk_number=disk.disk_number,
            storage=disk.storage_pool,
            size_gb=disk.size_gb,
            disk_format=disk.disk_format
        )

        disk.status = "ready"
        from datetime import datetime
        disk.attached_at = datetime.utcnow()
        disk.proxmox_disk_id = f"{disk.disk_interface}{disk.disk_number}"
        await db.commit()
        await db.refresh(disk)

        # Increment quota
        await quota_service.increment_usage(
            organization_id=org_context.org_id,
            storage_gb=disk.size_gb
        )

    except Exception as e:
        # Mark disk as error
        disk.status = "error"
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to attach disk to VM: {str(e)}"
        )

    return disk


@router.delete("/{vm_id}/disks/{disk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_disk_from_vm(
    vm_id: str,
    disk_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Detach and delete a disk from a VM.

    **Permissions Required:** VM_UPDATE
    **Note:** Cannot detach the boot disk
    """
    # Verify VM access
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only modify their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Get disk
    result = await db.execute(
        select(VMDisk).where(
            VMDisk.id == disk_id,
            VMDisk.vm_id == vm_id,
            VMDisk.deleted_at.is_(None)
        )
    )
    disk = result.scalar_one_or_none()

    if not disk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disk not found"
        )

    # Prevent deleting boot disk
    if disk.is_boot_disk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot detach the boot disk"
        )

    # Detach disk from Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)

        if disk.is_cdrom:
            # Unmount ISO from CD-ROM
            proxmox_service.unmount_iso_from_vm(
                node=vm.proxmox_node,
                vmid=vm.proxmox_vmid,
                disk_interface=disk.disk_interface,
                disk_number=disk.disk_number
            )
        else:
            # Remove regular disk from VM
            proxmox_service.detach_disk_from_vm(
                node=vm.proxmox_node,
                vmid=vm.proxmox_vmid,
                disk_interface=disk.disk_interface,
                disk_number=disk.disk_number
            )
    except Exception as e:
        # Log error but continue with soft delete
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to detach disk from Proxmox for disk {disk.id}: {e}")

    # Soft delete the disk record
    from datetime import datetime
    disk.deleted_at = datetime.utcnow()
    await db.commit()

    # Release quota
    if not disk.is_cdrom:
        from app.services.quota_service import QuotaService

        quota_service = QuotaService(db)
        await quota_service.decrement_usage(
            organization_id=vm.organization_id,
            storage_gb=disk.size_gb
        )

    return None


@router.post("/{vm_id}/disks/attach-iso", response_model=DiskResponse, status_code=status.HTTP_202_ACCEPTED)
async def attach_iso_to_vm(
    vm_id: str,
    iso_data: DiskAttachISO,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Attach an ISO image to a VM as a CD-ROM device.

    **Permissions Required:** VM_UPDATE
    """
    # Verify VM access
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only modify their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Verify ISO access
    result = await db.execute(
        select(ISOImage).where(
            ISOImage.id == iso_data.iso_image_id,
            ISOImage.deleted_at.is_(None)
        )
    )
    iso = result.scalar_one_or_none()

    if not iso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ISO image not found"
        )

    # Check ISO access
    if not iso.is_public and iso.organization_id != org_context.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this ISO image"
        )

    # Check if ISO is ready
    if iso.upload_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ISO is not ready (status: {iso.upload_status})"
        )

    # Check if VM already has an ide2 disk (CD-ROM slot) - including soft-deleted ones
    result = await db.execute(
        select(VMDisk).where(
            VMDisk.vm_id == vm_id,
            VMDisk.disk_interface == "ide",
            VMDisk.disk_number == 2
            # NOTE: Not filtering by deleted_at to find soft-deleted CD-ROMs
        )
    )
    existing_cdrom = result.scalar_one_or_none()

    if existing_cdrom:
        # Update existing CD-ROM with new ISO (restore if soft-deleted)
        existing_cdrom.iso_image_id = iso.id
        existing_cdrom.is_cdrom = True  # Ensure it's marked as CD-ROM
        existing_cdrom.status = "creating"
        existing_cdrom.deleted_at = None  # Restore if soft-deleted
        disk = existing_cdrom
    else:
        # Create new CD-ROM disk
        disk = VMDisk(
            vm_id=vm_id,
            disk_index=999,  # High number for CD-ROM
            disk_interface="ide",
            disk_number=2,
            storage_pool="",
            size_gb=0,
            is_boot_disk=False,
            is_cdrom=True,
            iso_image_id=iso.id,
            status="creating"
        )
        db.add(disk)

    await db.commit()
    await db.refresh(disk)

    # Mount ISO on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)

        proxmox_service.mount_iso_to_vm(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            iso_volid=iso.proxmox_volid,
            disk_interface="ide",
            disk_number=2
        )

        disk.status = "ready"
        from datetime import datetime
        disk.attached_at = datetime.utcnow()
        disk.proxmox_disk_id = "ide2"
        await db.commit()
        await db.refresh(disk)

    except Exception as e:
        disk.status = "error"
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to attach ISO to VM: {str(e)}"
        )

    return disk


@router.patch("/{vm_id}/disks/{disk_id}/resize", response_model=DiskResponse)
async def resize_vm_disk(
    vm_id: str,
    disk_id: str,
    resize_data: DiskResize,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resize a disk to a larger size.

    **Permissions Required:** VM_UPDATE
    **Note:** Can only increase disk size, not decrease
    """
    # Verify VM access
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only modify their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Get disk
    result = await db.execute(
        select(VMDisk).where(
            VMDisk.id == disk_id,
            VMDisk.vm_id == vm_id,
            VMDisk.deleted_at.is_(None)
        )
    )
    disk = result.scalar_one_or_none()

    if not disk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disk not found"
        )

    # Prevent resizing CD-ROM
    if disk.is_cdrom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resize CD-ROM disk"
        )

    # Validate new size is larger than current
    if resize_data.new_size_gb <= disk.size_gb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"New size must be larger than current size ({disk.size_gb}GB)"
        )

    # Check quota for additional storage
    from app.services.quota_service import QuotaService

    additional_storage_gb = resize_data.new_size_gb - disk.size_gb
    quota_service = QuotaService(db)
    quota_check = await quota_service.check_quota_availability(
        organization_id=org_context.org_id,
        storage_gb=additional_storage_gb
    )

    if not quota_check.is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quota exceeded: {', '.join(quota_check.exceeded_resources)}"
        )

    # Resize disk on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)

        proxmox_service.resize_disk(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            disk_interface=disk.disk_interface,
            disk_number=disk.disk_number,
            new_size_gb=resize_data.new_size_gb
        )

        # Update disk size in database
        old_size = disk.size_gb
        disk.size_gb = resize_data.new_size_gb
        await db.commit()
        await db.refresh(disk)

        # Increment quota for additional storage
        await quota_service.increment_usage(
            organization_id=org_context.org_id,
            storage_gb=additional_storage_gb
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resize disk: {str(e)}"
        )

    return disk
