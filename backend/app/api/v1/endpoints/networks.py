"""VPC Network management endpoints."""
from typing import Optional, List
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.models.user import User
from app.schemas.network import (
    NetworkCreate,
    NetworkUpdate,
    NetworkResponse,
    NetworkListResponse,
    IPPoolCreate,
    IPPoolResponse,
    IPAllocationRequest,
    IPAllocationResponse,
)
from app.core.deps import get_current_user, get_organization_context, OrgContext, RequirePermission
from app.core.rbac import Permission
from app.services.network_service import NetworkService
from app.services.ipam_service import IPAMService

router = APIRouter(prefix="/networks", tags=["VPC Networks"])


@router.post("", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
async def create_network(
    network_data: NetworkCreate,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    """Create VPC network with VLAN allocation.

    Automatically allocates VLAN from pool and checks quota limits.
    Gateway IP defaults to first usable IP in CIDR if not specified.

    **Required Permission**: network:create
    """
    network_service = NetworkService(db)

    try:
        network = await network_service.create_network(
            organization_id=org_context.org_id,
            created_by=org_context.user.id,
            network_data=network_data
        )
        return network

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=NetworkListResponse)
async def list_networks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_READ)),
    db: AsyncSession = Depends(get_db)
):
    """List VPC networks in organization.

    Returns paginated list of networks with VLAN assignments and configuration.

    **Required Permission**: network:read
    """
    network_service = NetworkService(db)

    skip = (page - 1) * per_page

    networks = await network_service.list_networks(
        organization_id=org_context.org_id,
        skip=skip,
        limit=per_page
    )

    total = await network_service.count_networks(org_context.org_id)
    total_pages = (total + per_page - 1) // per_page

    return NetworkListResponse(
        data=networks,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{network_id}", response_model=NetworkResponse)
async def get_network(
    network_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_READ)),
    db: AsyncSession = Depends(get_db)
):
    """Get network details by ID.

    **Required Permission**: network:read
    """
    network_service = NetworkService(db)

    network = await network_service.get_network(network_id, org_context.org_id)
    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found"
        )

    return network


@router.patch("/{network_id}", response_model=NetworkResponse)
async def update_network(
    network_id: str,
    update_data: NetworkUpdate,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Update network configuration.

    Note: CIDR and VLAN cannot be changed after creation.

    **Required Permission**: network:update
    """
    network_service = NetworkService(db)

    network = await network_service.update_network(
        network_id=network_id,
        organization_id=org_context.org_id,
        update_data=update_data
    )

    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found"
        )

    return network


@router.delete("/{network_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_network(
    network_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_DELETE)),
    db: AsyncSession = Depends(get_db)
):
    """Delete network and release VLAN.

    Fails if VMs are still attached to the network.

    **Required Permission**: network:delete
    """
    network_service = NetworkService(db)

    try:
        success = await network_service.delete_network(network_id, org_context.org_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Network {network_id} not found"
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{network_id}/set-default", response_model=NetworkResponse)
async def set_default_network(
    network_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Set network as default for organization.

    Only one network can be default per organization.

    **Required Permission**: network:update
    """
    network_service = NetworkService(db)

    try:
        network = await network_service.set_default_network(
            network_id=network_id,
            organization_id=org_context.org_id
        )
        return network

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{network_id}/stats")
async def get_network_stats(
    network_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_READ)),
    db: AsyncSession = Depends(get_db)
):
    """Get network statistics (IP usage, VM count, etc.).

    **Required Permission**: network:read
    """
    network_service = NetworkService(db)

    stats = await network_service.get_network_stats(network_id, org_context.org_id)

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found"
        )

    return stats


# ==================== IP Pool Management ====================

@router.post("/{network_id}/ip-pools", response_model=IPPoolResponse, status_code=status.HTTP_201_CREATED)
async def create_ip_pool(
    network_id: str,
    pool_data: IPPoolCreate,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Create IP pool within network.

    IP pool defines allocatable IP ranges for VMs.

    **Required Permission**: network:update
    """
    ipam_service = IPAMService(db)

    try:
        pool = await ipam_service.create_ip_pool(
            network_id=network_id,
            organization_id=org_context.org_id,
            pool_data=pool_data
        )
        return pool

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{network_id}/ip-pools", response_model=List[IPPoolResponse])
async def list_ip_pools(
    network_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_READ)),
    db: AsyncSession = Depends(get_db)
):
    """List IP pools in network.

    **Required Permission**: network:read
    """
    ipam_service = IPAMService(db)

    pools = await ipam_service.list_ip_pools(network_id, org_context.org_id)
    return pools


@router.delete("/ip-pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ip_pool(
    pool_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Delete IP pool.

    Fails if pool has active allocations.

    **Required Permission**: network:update
    """
    ipam_service = IPAMService(db)

    try:
        success = await ipam_service.delete_ip_pool(pool_id, org_context.org_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"IP pool {pool_id} not found"
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== IP Allocation Management ====================

@router.post("/{network_id}/allocate-ip", response_model=IPAllocationResponse, status_code=status.HTTP_201_CREATED)
async def allocate_ip(
    network_id: str,
    allocation_request: Optional[IPAllocationRequest] = None,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Allocate IP address from network.

    Allocation strategy:
    1. If preferred_ip specified, try to allocate it
    2. If ip_pool_id specified, allocate from that pool
    3. Otherwise, find first available IP

    **Required Permission**: network:update
    """
    ipam_service = IPAMService(db)

    try:
        allocation = await ipam_service.allocate_ip(
            network_id=network_id,
            organization_id=org_context.org_id,
            allocation_request=allocation_request
        )
        return allocation

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{network_id}/ip-allocations", response_model=List[IPAllocationResponse])
async def list_ip_allocations(
    network_id: str,
    status_filter: Optional[str] = Query(None, description="Filter by status (allocated, released, reserved)"),
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_READ)),
    db: AsyncSession = Depends(get_db)
):
    """List IP allocations in network.

    **Required Permission**: network:read
    """
    ipam_service = IPAMService(db)

    allocations = await ipam_service.list_allocations(
        network_id=network_id,
        organization_id=org_context.org_id,
        status=status_filter
    )
    return allocations


@router.delete("/ip-allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release_ip(
    allocation_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.NETWORK_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Release IP allocation.

    **Required Permission**: network:update
    """
    ipam_service = IPAMService(db)

    success = await ipam_service.release_ip(allocation_id, org_context.org_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IP allocation {allocation_id} not found"
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
