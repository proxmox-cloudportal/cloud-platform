"""
API endpoints for Proxmox Cluster management.
"""
from typing import Optional
from uuid import UUID
import uuid as uuid_lib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.proxmox_cluster import ProxmoxCluster
from app.models.virtual_machine import VirtualMachine
from app.models.organization import Organization
from app.models.user import User
from app.schemas.proxmox_cluster import (
    ProxmoxClusterCreate,
    ProxmoxClusterUpdate,
    ProxmoxClusterResponse,
    ProxmoxClusterListResponse,
    ClusterTestRequest,
    ClusterTestResponse,
)
from app.core.deps import get_current_user, get_current_superadmin
from app.services.proxmox_service import ProxmoxService

router = APIRouter(prefix="/clusters", tags=["Proxmox Clusters"])


@router.get("", response_model=ProxmoxClusterListResponse)
async def list_clusters(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ProxmoxClusterListResponse:
    """
    List all Proxmox clusters with pagination and filtering.
    Only superadmins can view all clusters.
    """
    # Build query
    query = select(ProxmoxCluster).where(ProxmoxCluster.deleted_at.is_(None))

    # Apply filters
    if is_active is not None:
        query = query.where(ProxmoxCluster.is_active == is_active)

    if search:
        query = query.where(ProxmoxCluster.name.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(ProxmoxCluster.created_at.desc())

    # Execute query
    result = await db.execute(query)
    clusters = result.scalars().all()

    return ProxmoxClusterListResponse(
        items=clusters,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page
    )


@router.post("", response_model=ProxmoxClusterResponse, status_code=status.HTTP_201_CREATED)
async def create_cluster(
    cluster_data: ProxmoxClusterCreate,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db)
) -> ProxmoxCluster:
    """
    Create a new Proxmox cluster.
    Only superadmins can create clusters.
    """
    # Check if cluster with same name already exists
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.name == cluster_data.name,
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A cluster with this name already exists"
        )

    # Create cluster (shared by default for all organizations)
    cluster = ProxmoxCluster(
        name=cluster_data.name,
        datacenter=cluster_data.datacenter,
        region=cluster_data.region,
        api_url=cluster_data.api_url,
        api_username=cluster_data.api_username,
        api_token_id=cluster_data.api_token_id,
        verify_ssl=cluster_data.verify_ssl,
        is_active=cluster_data.is_active,
        is_shared=True,  # Shared across all organizations by default
        organization_id=None,  # Not org-specific
    )

    # Store credentials (encrypted in production)
    if cluster_data.api_token_secret:
        cluster.api_token_secret_encrypted = cluster_data.api_token_secret
    if cluster_data.api_password:
        cluster.api_password_encrypted = cluster_data.api_password

    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)

    return cluster


@router.get("/{cluster_id}", response_model=ProxmoxClusterResponse)
async def get_cluster(
    cluster_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ProxmoxCluster:
    """Get details of a specific Proxmox cluster."""
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.id == str(cluster_id),
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    return cluster


@router.patch("/{cluster_id}", response_model=ProxmoxClusterResponse)
async def update_cluster(
    cluster_id: UUID,
    cluster_update: ProxmoxClusterUpdate,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db)
) -> ProxmoxCluster:
    """
    Update a Proxmox cluster.
    Only superadmins can update clusters.
    """
    # Get cluster
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.id == str(cluster_id),
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    # Update fields
    update_data = cluster_update.model_dump(exclude_unset=True)

    # Handle credential updates
    if "api_token_secret" in update_data and update_data["api_token_secret"]:
        cluster.api_token_secret_encrypted = update_data.pop("api_token_secret")
    if "api_password" in update_data and update_data["api_password"]:
        cluster.api_password_encrypted = update_data.pop("api_password")

    for field, value in update_data.items():
        setattr(cluster, field, value)

    await db.commit()
    await db.refresh(cluster)

    return cluster


@router.delete("/{cluster_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cluster(
    cluster_id: UUID,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a Proxmox cluster (soft delete).
    Only superadmins can delete clusters.
    """
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.id == str(cluster_id),
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    # Soft delete
    from datetime import datetime
    cluster.deleted_at = datetime.utcnow()
    await db.commit()

    return None


@router.post("/test", response_model=ClusterTestResponse)
async def test_cluster_connection(
    test_data: ClusterTestRequest,
    current_user: User = Depends(get_current_superadmin)
) -> ClusterTestResponse:
    """
    Test connection to a Proxmox cluster.
    Only superadmins can test cluster connections.
    """
    try:
        # Create temporary Proxmox service
        proxmox = ProxmoxService(
            host=test_data.api_url.replace("https://", "").replace("http://", "").split(":")[0],
            user=test_data.api_username,
            token_name=test_data.api_token_id,
            token_value=test_data.api_token_secret,
            password=test_data.api_password,
            verify_ssl=test_data.verify_ssl
        )

        # Test connection first
        connection_ok = proxmox.test_connection()

        if not connection_ok:
            return ClusterTestResponse(
                success=False,
                message="Failed to connect to Proxmox cluster. Please check your credentials and network connectivity."
            )

        # If connection successful, get additional info
        version_info = proxmox.get_version()
        nodes = proxmox.get_nodes()

        # Validate that we actually got data
        if not version_info and not nodes:
            return ClusterTestResponse(
                success=False,
                message="Connected but failed to retrieve cluster information. Please check API permissions."
            )

        node_names = [node.get("node") for node in nodes] if nodes else []

        return ClusterTestResponse(
            success=True,
            message="Successfully connected to Proxmox cluster",
            version=version_info.get("version") if version_info else None,
            nodes=node_names
        )
    except Exception as e:
        return ClusterTestResponse(
            success=False,
            message=f"Failed to connect: {str(e)}"
        )


@router.post("/{cluster_id}/sync", response_model=ProxmoxClusterResponse)
async def sync_cluster_resources(
    cluster_id: UUID,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db)
) -> ProxmoxCluster:
    """
    Sync cluster resources (CPU, memory, storage) from Proxmox.
    Only superadmins can sync cluster resources.
    """
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.id == str(cluster_id),
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )

    try:
        # Create Proxmox service
        proxmox = ProxmoxService(
            host=cluster.api_url.replace("https://", "").replace("http://", "").split(":")[0],
            user=cluster.api_username,
            token_name=cluster.api_token_id,
            token_value=cluster.api_token_secret_encrypted,
            password=cluster.api_password_encrypted,
            verify_ssl=cluster.verify_ssl
        )

        # Get cluster resources
        nodes = proxmox.get_nodes()

        # Calculate totals
        total_cpu_cores = sum(node.get("maxcpu", 0) for node in nodes) if nodes else 0
        total_memory_mb = sum(node.get("maxmem", 0) for node in nodes) // (1024 * 1024) if nodes else 0

        # Update cluster
        from datetime import datetime
        cluster.total_cpu_cores = total_cpu_cores
        cluster.total_memory_mb = total_memory_mb
        cluster.last_sync = datetime.utcnow()

        await db.commit()
        await db.refresh(cluster)

        return cluster
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync cluster: {str(e)}"
        )


@router.post("/{cluster_id}/sync-vms")
async def sync_cluster_vms(
    cluster_id: UUID,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Discover all VMs from Proxmox and upsert them into the portal DB.
    VMs are assigned to the default organization. Only superadmins can run this.
    """
    result = await db.execute(
        select(ProxmoxCluster).where(
            ProxmoxCluster.id == str(cluster_id),
            ProxmoxCluster.deleted_at.is_(None)
        )
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")

    # Resolve default org
    result = await db.execute(
        select(Organization).where(
            Organization.slug == "default",
            Organization.deleted_at.is_(None)
        )
    )
    default_org = result.scalar_one_or_none()
    if not default_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No default organization found. Create one first."
        )

    proxmox = ProxmoxService(cluster=cluster)
    nodes = proxmox.get_nodes()
    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach any nodes in this cluster."
        )

    added = updated = 0

    status_map = {"running": "running", "stopped": "stopped", "paused": "paused"}
    proxmox_conn = proxmox._get_connection()

    for node in nodes:
        node_name = node.get("node")
        if not node_name or node.get("status") != "online":
            continue

        # Fetch both QEMU VMs and LXC containers
        resources: list[tuple[str, list]] = []
        for vm_type, endpoint in [("qemu", proxmox_conn.nodes(node_name).qemu),
                                   ("lxc", proxmox_conn.nodes(node_name).lxc)]:
            try:
                resources.append((vm_type, endpoint.get()))
            except Exception:
                continue

        for vm_type, items in resources:
            for vm_data in items:
                vmid = vm_data.get("vmid")
                if not vmid:
                    continue

                result = await db.execute(
                    select(VirtualMachine).where(
                        VirtualMachine.proxmox_cluster_id == str(cluster_id),
                        VirtualMachine.proxmox_vmid == vmid,
                        VirtualMachine.vm_type == vm_type,
                        VirtualMachine.deleted_at.is_(None)
                    )
                )
                existing = result.scalar_one_or_none()
                portal_status = status_map.get(vm_data.get("status", "stopped"), "stopped")

                if existing:
                    existing.name = vm_data.get("name", existing.name)
                    existing.cpu_cores = vm_data.get("cpus", existing.cpu_cores)
                    existing.memory_mb = (vm_data.get("maxmem", 0) or 0) // (1024 * 1024)
                    existing.status = portal_status
                    existing.proxmox_node = node_name
                    updated += 1
                else:
                    vm = VirtualMachine(
                        id=str(uuid_lib.uuid4()),
                        organization_id=default_org.id,
                        owner_id=current_user.id,
                        proxmox_cluster_id=str(cluster_id),
                        proxmox_node=node_name,
                        proxmox_vmid=vmid,
                        vm_type=vm_type,
                        name=vm_data.get("name", f"{vm_type}-{vmid}"),
                        cpu_cores=vm_data.get("cpus", 1),
                        cpu_sockets=1,
                        memory_mb=(vm_data.get("maxmem", 0) or 0) // (1024 * 1024),
                        status=portal_status,
                        provisioned_at=datetime.utcnow(),
                    )
                    db.add(vm)
                    added += 1

    await db.commit()

    return {"added": added, "updated": updated, "nodes_scanned": len(nodes)}
