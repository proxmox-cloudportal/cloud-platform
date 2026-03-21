"""
VM Snapshot management endpoints.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.virtual_machine import VirtualMachine
from app.models.user import User
from app.schemas.snapshot import (
    SnapshotCreate,
    SnapshotResponse,
    SnapshotListResponse,
)
from app.core.deps import get_current_user, OrgContext, RequirePermission
from app.core.rbac import Role, Permission
from app.services.proxmox_service import ProxmoxService

router = APIRouter(prefix="/vms", tags=["VM Snapshots"])


@router.get("/{vm_id}/snapshots", response_model=SnapshotListResponse)
async def list_vm_snapshots(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    List all snapshots for a VM.

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

    # Get snapshots from Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        snapshots = proxmox_service.list_snapshots(vm.proxmox_node, vm.proxmox_vmid)

        # Filter out the "current" pseudo-snapshot
        snapshots = [s for s in snapshots if s.get("name") != "current"]

        return SnapshotListResponse(
            data=snapshots,
            total=len(snapshots)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list snapshots: {str(e)}"
        )


@router.post("/{vm_id}/snapshots", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def create_vm_snapshot(
    vm_id: str,
    snapshot_data: SnapshotCreate,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a snapshot of a VM.

    **Permissions Required:** VM_UPDATE
    **Note:** Snapshot names must be unique per VM
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

    # Create snapshot on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)

        result = proxmox_service.create_snapshot(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            snapshot_name=snapshot_data.name,
            description=snapshot_data.description,
            include_memory=snapshot_data.include_memory
        )

        return {
            "message": "Snapshot created successfully",
            "snapshot_name": snapshot_data.name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create snapshot: {str(e)}"
        )


@router.post("/{vm_id}/snapshots/{snapshot_name}/rollback", response_model=dict)
async def rollback_vm_snapshot(
    vm_id: str,
    snapshot_name: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Rollback VM to a specific snapshot.

    **Permissions Required:** VM_UPDATE
    **Warning:** This will revert the VM to the state it was in when the snapshot was taken
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

    # Rollback on Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)

        result = proxmox_service.rollback_snapshot(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            snapshot_name=snapshot_name
        )

        return {
            "message": f"VM rolled back to snapshot '{snapshot_name}' successfully",
            "snapshot_name": snapshot_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback snapshot: {str(e)}"
        )


@router.delete("/{vm_id}/snapshots/{snapshot_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vm_snapshot(
    vm_id: str,
    snapshot_name: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_UPDATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a VM snapshot.

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

    # Delete snapshot from Proxmox
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)

        proxmox_service.delete_snapshot(
            node=vm.proxmox_node,
            vmid=vm.proxmox_vmid,
            snapshot_name=snapshot_name
        )

        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete snapshot: {str(e)}"
        )
