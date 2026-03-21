"""
Storage Pool management endpoints for discovering and listing storage pools.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, Text

from app.db.session import get_db
from app.models.proxmox_cluster import ProxmoxCluster
from app.models.storage_pool import StoragePool
from app.schemas.storage_pool import (
    StoragePoolResponse,
    StoragePoolListResponse,
    StoragePoolSyncResponse,
)
from app.core.deps import get_current_user, OrgContext, RequirePermission
from app.core.rbac import Permission
from app.models.user import User
from app.tasks.sync_tasks import sync_storage_pools_for_cluster

router = APIRouter(prefix="/storage", tags=["Storage Pools"])


@router.get("/clusters/{cluster_id}/pools", response_model=StoragePoolListResponse)
async def list_storage_pools(
    cluster_id: str,
    content_type: str = None,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    """
    List storage pools for a Proxmox cluster.

    Optionally filter by content type (images, iso, backup).

    **Permissions Required:** VM_CREATE
    """
    # Verify cluster access
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.id == cluster_id,
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxmox cluster not found"
        )

    # Check access permissions
    if not cluster.is_shared and cluster.organization_id != org_context.org_id:
        if not org_context.is_superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this cluster"
            )

    # Build query
    query = select(StoragePool).where(
        StoragePool.proxmox_cluster_id == cluster_id,
        StoragePool.deleted_at.is_(None),
        StoragePool.is_active == True
    )

    # Filter by content type if provided
    if content_type:
        # Cast JSON to text and use text contains for compatibility
        query = query.where(
            cast(StoragePool.content_types, Text).contains(f'"{content_type}"')
        )

    query = query.order_by(StoragePool.storage_name)

    # Execute query
    result = await db.execute(query)
    pools = list(result.scalars().all())

    return StoragePoolListResponse(
        data=pools,
        total=len(pools)
    )


@router.get("/clusters/{cluster_id}/pools/{pool_id}", response_model=StoragePoolResponse)
async def get_storage_pool(
    cluster_id: str,
    pool_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get storage pool details.

    **Permissions Required:** VM_CREATE
    """
    # Verify cluster access
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.id == cluster_id,
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxmox cluster not found"
        )

    # Check access permissions
    if not cluster.is_shared and cluster.organization_id != org_context.org_id:
        if not org_context.is_superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this cluster"
            )

    # Get storage pool
    result = await db.execute(
        select(StoragePool).where(
            StoragePool.id == pool_id,
            StoragePool.proxmox_cluster_id == cluster_id,
            StoragePool.deleted_at.is_(None)
        )
    )
    pool = result.scalar_one_or_none()

    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storage pool not found"
        )

    return pool


@router.post("/clusters/{cluster_id}/pools/sync", response_model=StoragePoolSyncResponse)
async def sync_storage_pools(
    cluster_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.CLUSTER_SYNC)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync storage pools from Proxmox cluster.

    Queries the cluster and updates the database with current storage information.

    **Permissions Required:** CLUSTER_SYNC (superadmin only)
    """
    # Verify cluster exists
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.id == cluster_id,
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxmox cluster not found"
        )

    # Perform sync
    try:
        result = sync_storage_pools_for_cluster(cluster_id)

        return StoragePoolSyncResponse(
            synced_pools=result.get("synced_pools", 0),
            added=result.get("added", 0),
            updated=result.get("updated", 0),
            deactivated=result.get("deactivated", 0),
            message=f"Successfully synced {result.get('synced_pools', 0)} storage pools from cluster {cluster.name}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync storage pools: {str(e)}"
        )


@router.get("/pools", response_model=StoragePoolListResponse)
async def list_all_accessible_storage_pools(
    content_type: str = None,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    """
    List all storage pools accessible to the organization.

    Includes pools from shared clusters and organization-specific clusters.
    Optionally filter by content type (images, iso, backup).

    **Permissions Required:** VM_CREATE
    """
    # Get accessible clusters
    from sqlalchemy import or_

    cluster_query = select(ProxmoxCluster).where(
        ProxmoxCluster.is_active == True,
        ProxmoxCluster.deleted_at.is_(None),
        or_(
            ProxmoxCluster.is_shared == True,
            ProxmoxCluster.organization_id == org_context.org_id
        )
    )

    result = await db.execute(cluster_query)
    clusters = list(result.scalars().all())

    if not clusters:
        return StoragePoolListResponse(data=[], total=0)

    cluster_ids = [c.id for c in clusters]

    # Build query for storage pools
    query = select(StoragePool).where(
        StoragePool.proxmox_cluster_id.in_(cluster_ids),
        StoragePool.deleted_at.is_(None),
        StoragePool.is_active == True
    )

    # Filter by content type if provided
    if content_type:
        # Cast JSON to text and use text contains for compatibility
        query = query.where(
            cast(StoragePool.content_types, Text).contains(f'"{content_type}"')
        )

    query = query.order_by(StoragePool.proxmox_cluster_id, StoragePool.storage_name)

    # Execute query
    result = await db.execute(query)
    pools = list(result.scalars().all())

    return StoragePoolListResponse(
        data=pools,
        total=len(pools)
    )
