"""
Virtual Machine management endpoints.
"""
from typing import Optional
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.models.user import User
from app.models.virtual_machine import VirtualMachine
from app.models.proxmox_cluster import ProxmoxCluster
from app.models.vm_disk import VMDisk
from app.models.iso_image import ISOImage
from app.schemas.virtual_machine import (
    VMCreate,
    VMUpdate,
    VMResponse,
    VMListResponse,
    VMActionRequest,
    VMStatsResponse,
    VMResize,
)
from app.core.deps import get_current_user, get_organization_context, OrgContext, RequirePermission
from app.core.rbac import Role, Permission
from app.services.proxmox_service import ProxmoxService
from app.services.quota_service import QuotaService

router = APIRouter(prefix="/vms", tags=["Virtual Machines"])


def map_ostype_to_proxmox(ostype: Optional[str]) -> str:
    """
    Map user-friendly OS type to Proxmox ostype codes.

    Proxmox valid values:
    - other, wxp, w2k, w2k3, w2k8, wvista, win7, win8, win10, win11
    - l24, l26, solaris
    """
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
        return "l26"  # Default to Linux 2.6+

    # If already a valid Proxmox code, return as-is
    valid_proxmox_codes = ["other", "wxp", "w2k", "w2k3", "w2k8", "wvista",
                          "win7", "win8", "win10", "win11", "l24", "l26", "solaris"]
    if ostype in valid_proxmox_codes:
        return ostype

    # Map user-friendly name to Proxmox code
    return ostype_map.get(ostype.lower(), "l26")


async def provision_vm_task(
    vm_id: str,
    cluster_id: str,
    vm_data: dict,
    db_url: str
):
    """
    Background task to provision VM on Proxmox.
    In production, this should be a Celery task.
    """
    # This is a placeholder for async VM provisioning
    # In production, implement as Celery task
    pass


@router.get("", response_model=VMListResponse)
async def list_vms(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=500),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name"),
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List virtual machines in organization.

    - Org admins and superadmins see all VMs in the organization
    - Org members see only their own VMs
    - Org viewers see all VMs (read-only)

    Requires: VM_READ permission
    """
    # Build query - filter by organization
    query = select(VirtualMachine).where(
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members only see their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    # Apply filters
    if status:
        query = query.where(VirtualMachine.status == status)

    if search:
        search_filter = f"%{search}%"
        query = query.where(VirtualMachine.name.ilike(search_filter))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(VirtualMachine.created_at.desc())

    # Execute query
    result = await db.execute(query)
    vms = result.scalars().all()

    return {
        "data": vms,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@router.post("", response_model=VMResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_vm(
    vm_data: VMCreate,
    background_tasks: BackgroundTasks,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_CREATE)),
    db: AsyncSession = Depends(get_db)
) -> VirtualMachine:
    """
    Create a new virtual machine with multi-disk support and quota enforcement.

    The VM will be provisioned asynchronously on Proxmox via Celery task.
    Supports multiple disks with per-disk storage pool selection and ISO boot.

    Requires: VM_CREATE permission
    """
    # 1. Calculate total storage from all disks
    total_storage_gb = sum(disk.size_gb for disk in vm_data.disks)

    # 1.1. Validate ISO access if provided
    iso_image = None
    if vm_data.iso_image_id:
        result = await db.execute(
            select(ISOImage).where(
                ISOImage.id == vm_data.iso_image_id,
                ISOImage.deleted_at.is_(None)
            )
        )
        iso_image = result.scalar_one_or_none()

        if not iso_image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ISO image not found"
            )

        # Check ISO access permissions
        if not iso_image.is_public and iso_image.organization_id != org_context.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ISO image"
            )

        # Ensure ISO is ready
        if iso_image.upload_status != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ISO is not ready yet (status: {iso_image.upload_status})"
            )

    # 1.2. Check quota availability BEFORE creating VM
    quota_service = QuotaService(db)

    quota_check = await quota_service.check_quota_availability(
        organization_id=org_context.org_id,
        cpu_cores=vm_data.cpu_cores,
        memory_gb=vm_data.memory_mb / 1024,
        storage_gb=total_storage_gb,
        vm_count=1
    )

    if not quota_check.is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quota exceeded: {', '.join(quota_check.exceeded_resources)}"
        )

    # 2. Select cluster (must be accessible by organization)
    if vm_data.proxmox_cluster_id:
        result = await db.execute(
            select(ProxmoxCluster).where(
                ProxmoxCluster.id == vm_data.proxmox_cluster_id,
                ProxmoxCluster.is_active == True,
                ProxmoxCluster.deleted_at.is_(None),
                or_(
                    ProxmoxCluster.organization_id == org_context.org_id,
                    ProxmoxCluster.is_shared == True
                )
            )
        )
        cluster = result.scalar_one_or_none()
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proxmox cluster not found or not accessible by your organization"
            )
    else:
        # Auto-select: prefer org-specific, fallback to shared
        result = await db.execute(
            select(ProxmoxCluster).where(
                ProxmoxCluster.is_active == True,
                ProxmoxCluster.deleted_at.is_(None),
                or_(
                    ProxmoxCluster.organization_id == org_context.org_id,
                    ProxmoxCluster.is_shared == True
                )
            ).order_by(
                # Prefer org-specific clusters
                ProxmoxCluster.organization_id == org_context.org_id,
                ProxmoxCluster.load_score.asc()
            ).limit(1)
        )
        cluster = result.scalar_one_or_none()
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No active Proxmox clusters available for your organization"
            )

    # Get next VMID from Proxmox
    proxmox_service = ProxmoxService(cluster)
    try:
        proxmox_vmid = proxmox_service.get_next_vmid()
        best_node = proxmox_service.select_best_node()
        if not best_node:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No available nodes in Proxmox cluster"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to Proxmox cluster: {str(e)}"
        )

    # 2.1. Validate network access if provided
    if vm_data.network_id:
        from app.models.vpc_network import VPCNetwork
        result = await db.execute(
            select(VPCNetwork).where(
                VPCNetwork.id == vm_data.network_id,
                VPCNetwork.deleted_at.is_(None),
                or_(
                    VPCNetwork.organization_id == org_context.org_id,
                    VPCNetwork.is_shared == True
                )
            )
        )
        network = result.scalar_one_or_none()
        if not network:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Network not found or not accessible by your organization"
            )

    # 3. Create VM record in database
    vm = VirtualMachine(
        name=vm_data.name,
        hostname=vm_data.hostname,
        description=vm_data.description,
        organization_id=org_context.org_id,
        owner_id=org_context.user.id,
        proxmox_cluster_id=cluster.id,
        proxmox_vmid=proxmox_vmid,
        proxmox_node=best_node,
        cpu_cores=vm_data.cpu_cores,
        cpu_sockets=vm_data.cpu_sockets,
        memory_mb=vm_data.memory_mb,
        os_type=vm_data.os_type,
        status="provisioning",
        tags=vm_data.tags or [],
        network_id=vm_data.network_id,  # Store network for Celery task
    )

    db.add(vm)
    await db.flush()  # Flush to get VM ID

    # 3.1. Create disk records
    default_storage = "local-lvm"  # Default storage pool
    for idx, disk_spec in enumerate(vm_data.disks):
        disk = VMDisk(
            vm_id=vm.id,
            disk_index=idx,
            disk_interface=disk_spec.disk_interface,
            disk_number=idx,
            storage_pool=disk_spec.storage_pool or default_storage,
            size_gb=disk_spec.size_gb,
            disk_format=disk_spec.disk_format,
            is_boot_disk=disk_spec.is_boot_disk,
            is_cdrom=False,
            status="creating"
        )
        db.add(disk)

    # 3.2. Create CD-ROM disk for ISO if provided
    if iso_image:
        cdrom_disk = VMDisk(
            vm_id=vm.id,
            disk_index=len(vm_data.disks),
            disk_interface="ide",
            disk_number=2,
            storage_pool="",  # CD-ROM doesn't need storage pool
            size_gb=0,  # CD-ROM has no size
            disk_format=None,
            is_boot_disk=False,
            is_cdrom=True,
            iso_image_id=iso_image.id,
            status="creating"
        )
        db.add(cdrom_disk)

    await db.commit()
    await db.refresh(vm)

    # 4. Increment quota usage
    await quota_service.increment_usage(
        organization_id=org_context.org_id,
        cpu_cores=vm_data.cpu_cores,
        memory_gb=vm_data.memory_mb / 1024,
        storage_gb=total_storage_gb,
        vm_count=1
    )

    # 5. Queue VM provisioning task (Celery)
    try:
        from app.tasks.vm_tasks import provision_vm_with_disks

        # Queue the provisioning task
        provision_vm_with_disks.delay(str(vm.id))

        logger.info(f"VM {vm.id} provisioning queued with {len(vm_data.disks)} disk(s)")

    except Exception as e:
        logger.error(f"Failed to queue VM provisioning task: {e}")
        # Mark VM as error but don't fail the request
        # The VM record exists and quota is reserved
        vm.status = "error"
        await db.commit()

    return vm


@router.get("/{vm_id}", response_model=VMResponse)
async def get_vm(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db)
) -> VirtualMachine:
    """
    Get VM details by ID.

    Members can only view their own VMs.
    Admins and viewers can view all org VMs.

    Requires: VM_READ permission
    """
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

    return vm


@router.patch("/{vm_id}", response_model=VMResponse)
async def update_vm(
    vm_id: str,
    vm_update: VMUpdate,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    db: AsyncSession = Depends(get_db)
) -> VirtualMachine:
    """
    Update VM configuration.

    Members can only update their own VMs.
    Admins can update any VM in the organization.

    Requires: VM_UPDATE permission
    """
    # Get VM
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only update their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found"
        )

    # Update fields
    if vm_update.name is not None:
        vm.name = vm_update.name
    if vm_update.hostname is not None:
        vm.hostname = vm_update.hostname
    if vm_update.description is not None:
        vm.description = vm_update.description
    if vm_update.cpu_cores is not None:
        vm.cpu_cores = vm_update.cpu_cores
    if vm_update.memory_mb is not None:
        vm.memory_mb = vm_update.memory_mb

    await db.commit()
    await db.refresh(vm)

    return vm


@router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vm(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_DELETE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a VM and release quota.

    Members can only delete their own VMs.
    Admins can delete any VM in the organization.

    Requires: VM_DELETE permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only delete their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Get disks to calculate storage for quota release
    result = await db.execute(
        select(VMDisk).where(
            VMDisk.vm_id == vm_id,
            VMDisk.deleted_at.is_(None),
            VMDisk.is_cdrom == False
        )
    )
    disks = list(result.scalars().all())

    # Calculate total storage from disks
    total_storage_gb = sum(disk.size_gb for disk in disks) if disks else 20  # Fallback to 20
    cpu_cores = vm.cpu_cores
    memory_gb = vm.memory_mb / 1024

    # Delete from Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        proxmox_service.delete_vm(vm.proxmox_node, vm.proxmox_vmid)
    except Exception as e:
        # Log error but continue with soft delete
        print(f"Failed to delete VM from Proxmox: {e}")

    # Soft delete
    vm.deleted_at = datetime.utcnow()
    await db.commit()

    # Soft delete disk records
    for disk in disks:
        disk.deleted_at = datetime.utcnow()

    # Release quota
    quota_service = QuotaService(db)
    await quota_service.decrement_usage(
        organization_id=vm.organization_id,
        cpu_cores=cpu_cores,
        memory_gb=memory_gb,
        storage_gb=total_storage_gb,
        vm_count=1
    )

    return None


@router.post("/{vm_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_vm(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_START)),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Start a VM.

    Requires: VM_START permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only start their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Start VM on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        result = proxmox_service.start_vm(vm.proxmox_node, vm.proxmox_vmid)

        # Update status
        vm.status = "running"
        vm.power_state = "on"
        vm.started_at = datetime.utcnow()
        await db.commit()

        return {
            "message": "VM start initiated",
            "task_id": result.get("task_id")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start VM: {str(e)}"
        )


@router.post("/{vm_id}/stop", status_code=status.HTTP_202_ACCEPTED)
async def stop_vm(
    vm_id: str,
    action_data: VMActionRequest = VMActionRequest(),
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_STOP)),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Stop a VM.

    Requires: VM_STOP permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only stop their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Stop VM on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        result = proxmox_service.stop_vm(vm.proxmox_node, vm.proxmox_vmid, force=action_data.force)

        # Update status
        vm.status = "stopped"
        vm.power_state = "off"
        vm.stopped_at = datetime.utcnow()
        await db.commit()

        return {
            "message": "VM stop initiated",
            "task_id": result.get("task_id")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop VM: {str(e)}"
        )


@router.post("/{vm_id}/restart", status_code=status.HTTP_202_ACCEPTED)
async def restart_vm(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_RESTART)),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Restart a VM.

    Requires: VM_RESTART permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only restart their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Restart VM on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        result = proxmox_service.restart_vm(vm.proxmox_node, vm.proxmox_vmid)

        return {
            "message": "VM restart initiated",
            "task_id": result.get("task_id")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart VM: {str(e)}"
        )


@router.get("/{vm_id}/console")
async def get_vm_console(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get noVNC console URL for a VM.

    Returns a URL that can be opened in a new window to access the VM's console.

    **Known Limitation:** Due to browser cross-domain security restrictions, users
    must be logged into the Proxmox web interface in a separate tab before the
    console will work. This is because Proxmox requires the PVEAuthCookie to be
    set as an actual HTTP cookie, which cannot be done cross-domain from JavaScript.

    **Workaround:**
    1. Open Proxmox web interface in a new tab (https://proxmox-server:8006)
    2. Log in with your credentials
    3. Return to this portal and click the Console button

    Requires: VM_READ permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only access their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Get console URL from Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        console_info = proxmox_service.get_console_url(vm.proxmox_node, vm.proxmox_vmid)

        # Extract Proxmox server URL for workaround instructions
        proxmox_url = console_info["console_url"]
        proxmox_host = proxmox_url.split("?")[0] if "?" in proxmox_url else proxmox_url

        return {
            "console_url": console_info["console_url"],
            "message": "Console URL generated successfully",
            "workaround_note": (
                f"If you see 'Error 401: No ticket', please log into Proxmox web interface first: {proxmox_host}"
            )
        }
    except Exception as e:
        logger.error(f"Failed to get console URL for VM {vm_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get console access: {str(e)}"
        )


@router.post("/{vm_id}/sync", response_model=VMResponse)
async def sync_vm_status(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db)
) -> VirtualMachine:
    """
    Sync VM status from Proxmox.

    Updates the VM status in the database to match the actual status in Proxmox.
    Useful for VMs stuck in "provisioning" status.

    Requires: VM_READ permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only sync their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Get status from Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        proxmox_status = proxmox_service.get_vm_status(vm.proxmox_node, vm.proxmox_vmid)

        # Update VM status based on Proxmox
        vm_status = proxmox_status.get("status", "unknown")
        vm.power_state = vm_status

        # Map Proxmox status to our status
        if vm_status == "running":
            vm.status = "running"
        elif vm_status == "stopped":
            vm.status = "stopped"
        elif vm_status == "paused":
            vm.status = "stopped"
        else:
            vm.status = "unknown"

        # Update IP if available
        if proxmox_status.get("ip"):
            vm.primary_ip_address = proxmox_status.get("ip")

        await db.commit()
        await db.refresh(vm)

        logger.info(f"Synced VM {vm.id} status from Proxmox: {vm_status}")
        return vm

    except Exception as e:
        logger.error(f"Failed to sync VM {vm.id} status: {e}")
        # If VM doesn't exist in Proxmox (404), mark as error
        if "404" in str(e) or "not found" in str(e).lower():
            vm.status = "error"
            await db.commit()
            await db.refresh(vm)
            return vm

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync VM status from Proxmox: {str(e)}"
        )


@router.post("/{vm_id}/force-stop", response_model=VMResponse)
async def force_stop_vm(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Force stop (shutdown) a VM immediately.

    This forces the VM to stop without waiting for a graceful shutdown.

    Requires: VM_UPDATE permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only force stop their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Force stop VM on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        proxmox_service.force_stop_vm(vm.proxmox_node, vm.proxmox_vmid)

        vm.status = "stopped"
        await db.commit()
        await db.refresh(vm)

        logger.info(f"Force stopped VM {vm.id}")
        return vm
    except Exception as e:
        logger.error(f"Failed to force stop VM {vm.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to force stop VM: {str(e)}"
        )


@router.post("/{vm_id}/reboot", response_model=VMResponse)
async def reboot_vm(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Reboot a VM.

    Sends a reboot signal to the VM.

    Requires: VM_UPDATE permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only reboot their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Reboot VM on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        proxmox_service.reboot_vm(vm.proxmox_node, vm.proxmox_vmid)

        logger.info(f"Rebooted VM {vm.id}")
        await db.refresh(vm)
        return vm
    except Exception as e:
        logger.error(f"Failed to reboot VM {vm.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reboot VM: {str(e)}"
        )


@router.post("/{vm_id}/reset", response_model=VMResponse)
async def reset_vm(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset a VM (hard reset).

    This performs a hard reset, similar to pressing the reset button on a physical computer.

    Requires: VM_UPDATE permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only reset their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Reset VM on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        proxmox_service.reset_vm(vm.proxmox_node, vm.proxmox_vmid)

        logger.info(f"Reset VM {vm.id}")
        await db.refresh(vm)
        return vm
    except Exception as e:
        logger.error(f"Failed to reset VM {vm.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset VM: {str(e)}"
        )


@router.patch("/{vm_id}/resize", response_model=VMResponse)
async def resize_vm_resources(
    vm_id: str,
    resize_data: VMResize,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Resize VM CPU and/or memory.

    **Note:** VM must be stopped to resize resources.
    **Permissions Required:** VM_UPDATE
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only resize their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # Verify at least one resource is specified
    if resize_data.cpu_cores is None and resize_data.cpu_sockets is None and resize_data.memory_mb is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one resource (CPU cores, CPU sockets, or memory) must be specified"
        )

    # Check quota for resource changes
    from app.services.quota_service import QuotaService

    quota_service = QuotaService(db)

    # Calculate deltas
    cpu_delta = 0
    memory_delta = 0

    if resize_data.cpu_cores is not None:
        cpu_delta = resize_data.cpu_cores - vm.cpu_cores

    if resize_data.memory_mb is not None:
        memory_delta = resize_data.memory_mb - vm.memory_mb

    # Check quota if resources are increasing
    if cpu_delta > 0 or memory_delta > 0:
        quota_check = await quota_service.check_quota_availability(
            organization_id=org_context.org_id,
            cpu_cores=cpu_delta if cpu_delta > 0 else 0,
            memory_gb=(memory_delta / 1024) if memory_delta > 0 else 0
        )

        if not quota_check.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quota exceeded: {', '.join(quota_check.exceeded_resources)}"
            )

    # Resize VM on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)

        proxmox_service.resize_vm(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            cpu_cores=resize_data.cpu_cores,
            cpu_sockets=resize_data.cpu_sockets,
            memory_mb=resize_data.memory_mb
        )

        # Update VM record
        if resize_data.cpu_cores is not None:
            vm.cpu_cores = resize_data.cpu_cores

        if resize_data.cpu_sockets is not None:
            vm.cpu_sockets = resize_data.cpu_sockets

        if resize_data.memory_mb is not None:
            vm.memory_mb = resize_data.memory_mb

        await db.commit()
        await db.refresh(vm)

        # Update quota
        if cpu_delta != 0 or memory_delta != 0:
            if cpu_delta > 0 or memory_delta > 0:
                await quota_service.increment_usage(
                    organization_id=org_context.org_id,
                    cpu_cores=cpu_delta if cpu_delta > 0 else 0,
                    memory_gb=(memory_delta / 1024) if memory_delta > 0 else 0
                )
            else:
                await quota_service.decrement_usage(
                    organization_id=org_context.org_id,
                    cpu_cores=abs(cpu_delta) if cpu_delta < 0 else 0,
                    memory_gb=(abs(memory_delta) / 1024) if memory_delta < 0 else 0
                )

        logger.info(f"Resized VM {vm.id}")
        return vm
    except Exception as e:
        logger.error(f"Failed to resize VM {vm.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resize VM: {str(e)}"
        )


# ==================== Network Management ====================

@router.post("/{vm_id}/attach-network", response_model=VMResponse)
async def attach_network_to_vm(
    vm_id: str,
    attach_request: dict,  # Using dict to avoid circular import, will validate inline
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_ATTACH)),
    db: AsyncSession = Depends(get_db)
):
    """Attach network to VM with VLAN configuration.

    Attaches a VPC network to VM, automatically applying VLAN tagging.
    Optionally allocates IP address from network pool.

    **Required Permission**: network:attach

    Request body:
    ```json
    {
        "network_id": "string",
        "interface_order": 0,  // 0-3 for net0-net3
        "model": "virtio",  // virtio, e1000, rtl8139
        "allocate_ip": true,
        "ip_pool_id": "optional_pool_id"
    }
    ```
    """
    from app.models.vpc_network import VPCNetwork
    from app.models.vm_network_interface import VMNetworkInterface
    from app.services.network_service import NetworkService
    from app.services.ipam_service import IPAMService
    from app.schemas.network import IPAllocationRequest

    # Validate request
    network_id = attach_request.get("network_id")
    interface_order = attach_request.get("interface_order", 0)
    model = attach_request.get("model", "virtio")
    allocate_ip = attach_request.get("allocate_ip", True)
    ip_pool_id = attach_request.get("ip_pool_id")

    if not network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="network_id is required"
        )

    if not (0 <= interface_order <= 3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="interface_order must be between 0 and 3"
        )

    if model not in ["virtio", "e1000", "rtl8139"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model must be one of: virtio, e1000, rtl8139"
        )

    # Get VM with permission check
    result = await db.execute(
        select(VirtualMachine).where(
            VirtualMachine.id == vm_id,
            VirtualMachine.organization_id == org_context.org_id,
            VirtualMachine.deleted_at.is_(None)
        )
    )
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VM {vm_id} not found"
        )

    # Get network
    network_service = NetworkService(db)
    network = await network_service.get_network(network_id, org_context.org_id)

    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found"
        )

    # Check if interface already exists
    interface_name = f"net{interface_order}"
    existing_result = await db.execute(
        select(VMNetworkInterface).where(
            VMNetworkInterface.vm_id == vm_id,
            VMNetworkInterface.interface_name == interface_name,
            VMNetworkInterface.deleted_at.is_(None)
        )
    )
    existing_interface = existing_result.scalar_one_or_none()

    if existing_interface:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interface {interface_name} already attached to VM"
        )

    # Check max interfaces (4)
    interfaces_result = await db.execute(
        select(func.count(VMNetworkInterface.id)).where(
            VMNetworkInterface.vm_id == vm_id,
            VMNetworkInterface.deleted_at.is_(None)
        )
    )
    interface_count = interfaces_result.scalar() or 0

    if interface_count >= 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 4 network interfaces per VM"
        )

    # Build Proxmox network config
    proxmox_service = ProxmoxService(vm.proxmox_cluster)
    net_config = proxmox_service.build_network_config(
        interface_name=interface_name,
        vlan_id=network.vlan_id,
        bridge=network.bridge,
        model=model
    )

    # Apply to Proxmox
    try:
        proxmox_service.attach_network_to_vm(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            interface_name=interface_name,
            vlan_id=network.vlan_id,
            bridge=network.bridge,
            model=model
        )
    except Exception as e:
        logger.error(f"Failed to attach network to Proxmox VM {vm.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to attach network on Proxmox: {str(e)}"
        )

    # Create interface record
    is_primary = (interface_count == 0)  # First interface is primary
    interface = VMNetworkInterface(
        vm_id=vm.id,
        network_id=network.id,
        interface_name=interface_name,
        interface_order=interface_order,
        model=model,
        is_primary=is_primary,
        proxmox_config=net_config
    )
    db.add(interface)
    await db.flush()

    # Allocate IP if requested
    if allocate_ip:
        ipam_service = IPAMService(db)
        try:
            allocation_request = IPAllocationRequest(
                ip_pool_id=ip_pool_id
            ) if ip_pool_id else None

            ip_allocation = await ipam_service.allocate_ip(
                network_id=network.id,
                organization_id=org_context.org_id,
                vm_id=vm.id,
                interface_name=interface_name,
                allocation_request=allocation_request
            )
            interface.ip_allocation_id = ip_allocation.id

            logger.info(
                f"Allocated IP {ip_allocation.ip_address} to VM {vm.id} "
                f"interface {interface_name}"
            )
        except ValueError as e:
            logger.warning(f"Could not allocate IP for VM {vm.id}: {e}")
            # Continue without IP allocation - not critical

    await db.commit()
    await db.refresh(vm)

    logger.info(
        f"Attached network {network.id} (VLAN {network.vlan_id}) to VM {vm.id} "
        f"as {interface_name}"
    )

    return vm


@router.delete("/{vm_id}/detach-network/{interface_name}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_network_from_vm(
    vm_id: str,
    interface_name: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Detach network interface from VM.

    Removes network interface and releases IP allocation.

    **Required Permission**: vm:update
    """
    from app.models.vm_network_interface import VMNetworkInterface
    from app.services.ipam_service import IPAMService

    # Validate interface name
    if interface_name not in ["net0", "net1", "net2", "net3"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="interface_name must be one of: net0, net1, net2, net3"
        )

    # Get VM with permission check
    result = await db.execute(
        select(VirtualMachine).where(
            VirtualMachine.id == vm_id,
            VirtualMachine.organization_id == org_context.org_id,
            VirtualMachine.deleted_at.is_(None)
        )
    )
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VM {vm_id} not found"
        )

    # Get interface
    interface_result = await db.execute(
        select(VMNetworkInterface).where(
            VMNetworkInterface.vm_id == vm_id,
            VMNetworkInterface.interface_name == interface_name,
            VMNetworkInterface.deleted_at.is_(None)
        )
    )
    interface = interface_result.scalar_one_or_none()

    if not interface:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interface {interface_name} not found on VM"
        )

    # Detach from Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        proxmox_service.detach_network_from_vm(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            interface_name=interface_name
        )
    except Exception as e:
        logger.error(f"Failed to detach network from Proxmox VM {vm.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detach network on Proxmox: {str(e)}"
        )

    # Release IP allocation if exists
    if interface.ip_allocation_id:
        ipam_service = IPAMService(db)
        await ipam_service.release_ip(
            interface.ip_allocation_id,
            org_context.org_id
        )

    # Soft delete interface
    interface.deleted_at = datetime.utcnow()

    await db.commit()

    logger.info(f"Detached network interface {interface_name} from VM {vm.id}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
