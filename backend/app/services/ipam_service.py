"""IPAM (IP Address Management) service for network IP allocation."""
from typing import Optional, List
import ipaddress
import logging
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vpc_network import VPCNetwork
from app.models.network_ip_pool import NetworkIPPool
from app.models.network_ip_allocation import NetworkIPAllocation
from app.schemas.network import IPPoolCreate, IPAllocationRequest

logger = logging.getLogger(__name__)


class IPAMService:
    """Service for IP address allocation and management within networks."""

    def __init__(self, db: AsyncSession):
        """Initialize IPAM service.

        Args:
            db: Database session
        """
        self.db = db

    async def create_ip_pool(
        self,
        network_id: str,
        organization_id: str,
        pool_data: IPPoolCreate
    ) -> NetworkIPPool:
        """Create IP pool within network.

        Args:
            network_id: Network ID
            organization_id: Organization ID for authorization
            pool_data: IP pool creation data

        Returns:
            Created NetworkIPPool

        Raises:
            ValueError: If network not found or IP range invalid

        Example:
            >>> pool = await ipam_service.create_ip_pool(
            ...     network_id="net-123",
            ...     organization_id="org-456",
            ...     pool_data=IPPoolCreate(
            ...         pool_name="VM Pool",
            ...         start_ip="10.100.0.10",
            ...         end_ip="10.100.0.250"
            ...     )
            ... )
        """
        # Verify network exists and belongs to organization
        result = await self.db.execute(
            select(VPCNetwork).where(
                and_(
                    VPCNetwork.id == network_id,
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
        )
        network = result.scalar_one_or_none()
        if not network:
            raise ValueError(f"Network {network_id} not found")

        # Validate IP addresses are within network CIDR
        network_obj = ipaddress.ip_network(network.cidr, strict=False)
        start_ip_obj = ipaddress.ip_address(pool_data.start_ip)
        end_ip_obj = ipaddress.ip_address(pool_data.end_ip)

        if start_ip_obj not in network_obj:
            raise ValueError(
                f"Start IP {pool_data.start_ip} not in network {network.cidr}"
            )

        if end_ip_obj not in network_obj:
            raise ValueError(
                f"End IP {pool_data.end_ip} not in network {network.cidr}"
            )

        if start_ip_obj >= end_ip_obj:
            raise ValueError("Start IP must be less than end IP")

        # Create IP pool
        ip_pool = NetworkIPPool(
            network_id=network_id,
            pool_name=pool_data.pool_name,
            start_ip=pool_data.start_ip,
            end_ip=pool_data.end_ip,
            description=pool_data.description
        )

        self.db.add(ip_pool)
        await self.db.commit()
        await self.db.refresh(ip_pool)

        logger.info(
            f"Created IP pool {ip_pool.id} ({pool_data.pool_name}) "
            f"for network {network_id}: {pool_data.start_ip}-{pool_data.end_ip}"
        )

        return ip_pool

    async def list_ip_pools(
        self,
        network_id: str,
        organization_id: str
    ) -> List[NetworkIPPool]:
        """List IP pools in network.

        Args:
            network_id: Network ID
            organization_id: Organization ID for authorization

        Returns:
            List of NetworkIPPool objects

        Example:
            >>> pools = await ipam_service.list_ip_pools("net-123", "org-456")
        """
        # Verify network access
        result = await self.db.execute(
            select(VPCNetwork).where(
                and_(
                    VPCNetwork.id == network_id,
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
        )
        network = result.scalar_one_or_none()
        if not network:
            return []

        # Get pools
        pools_result = await self.db.execute(
            select(NetworkIPPool)
            .where(
                and_(
                    NetworkIPPool.network_id == network_id,
                    NetworkIPPool.deleted_at.is_(None)
                )
            )
            .order_by(NetworkIPPool.created_at)
        )
        return list(pools_result.scalars().all())

    async def delete_ip_pool(
        self,
        pool_id: str,
        organization_id: str
    ) -> bool:
        """Delete IP pool.

        Args:
            pool_id: IP pool ID
            organization_id: Organization ID for authorization

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If pool has active allocations

        Example:
            >>> success = await ipam_service.delete_ip_pool("pool-123", "org-456")
        """
        # Get pool with network check
        result = await self.db.execute(
            select(NetworkIPPool)
            .join(VPCNetwork, NetworkIPPool.network_id == VPCNetwork.id)
            .where(
                and_(
                    NetworkIPPool.id == pool_id,
                    VPCNetwork.organization_id == organization_id,
                    NetworkIPPool.deleted_at.is_(None)
                )
            )
        )
        pool = result.scalar_one_or_none()
        if not pool:
            return False

        # Check for active allocations from this pool
        alloc_result = await self.db.execute(
            select(NetworkIPAllocation).where(
                and_(
                    NetworkIPAllocation.ip_pool_id == pool_id,
                    NetworkIPAllocation.status == "allocated",
                    NetworkIPAllocation.deleted_at.is_(None)
                )
            )
        )
        active_allocations = list(alloc_result.scalars().all())

        if active_allocations:
            raise ValueError(
                f"Cannot delete IP pool: {len(active_allocations)} "
                "active allocation(s) exist"
            )

        # Soft delete
        from datetime import datetime
        pool.deleted_at = datetime.utcnow()
        await self.db.commit()

        logger.info(f"Deleted IP pool {pool_id}")
        return True

    async def allocate_ip(
        self,
        network_id: str,
        organization_id: str,
        vm_id: Optional[str] = None,
        interface_name: Optional[str] = None,
        allocation_request: Optional[IPAllocationRequest] = None
    ) -> NetworkIPAllocation:
        """Allocate IP address from network.

        Allocation strategy:
        1. If preferred_ip specified, try to allocate it
        2. If ip_pool_id specified, allocate from that pool
        3. Otherwise, find first available IP in any pool or entire CIDR

        Args:
            network_id: Network ID
            organization_id: Organization ID for authorization
            vm_id: Optional VM ID to assign IP to
            interface_name: Optional interface name (net0, net1, etc.)
            allocation_request: Optional allocation preferences

        Returns:
            NetworkIPAllocation

        Raises:
            ValueError: If network not found or no IPs available

        Example:
            >>> allocation = await ipam_service.allocate_ip(
            ...     network_id="net-123",
            ...     organization_id="org-456",
            ...     vm_id="vm-789",
            ...     interface_name="net0"
            ... )
        """
        # Get network
        result = await self.db.execute(
            select(VPCNetwork).where(
                and_(
                    VPCNetwork.id == network_id,
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
        )
        network = result.scalar_one_or_none()
        if not network:
            raise ValueError(f"Network {network_id} not found")

        allocation_request = allocation_request or IPAllocationRequest()

        # Strategy 1: Preferred IP
        if allocation_request.preferred_ip:
            allocated_ip = await self._try_allocate_specific_ip(
                network=network,
                ip_address=allocation_request.preferred_ip,
                vm_id=vm_id,
                interface_name=interface_name,
                ip_pool_id=allocation_request.ip_pool_id
            )
            if allocated_ip:
                return allocated_ip
            else:
                raise ValueError(
                    f"Preferred IP {allocation_request.preferred_ip} not available"
                )

        # Strategy 2: From specific pool
        if allocation_request.ip_pool_id:
            allocated_ip = await self._allocate_from_pool(
                network=network,
                pool_id=allocation_request.ip_pool_id,
                vm_id=vm_id,
                interface_name=interface_name
            )
            if allocated_ip:
                return allocated_ip
            else:
                raise ValueError(
                    f"No available IPs in pool {allocation_request.ip_pool_id}"
                )

        # Strategy 3: From any pool or entire CIDR
        # Try pools first
        pools = await self.list_ip_pools(network_id, organization_id)
        for pool in pools:
            allocated_ip = await self._allocate_from_pool(
                network=network,
                pool_id=pool.id,
                vm_id=vm_id,
                interface_name=interface_name
            )
            if allocated_ip:
                return allocated_ip

        # No pools or all pools exhausted - try entire CIDR
        allocated_ip = await self._allocate_from_cidr(
            network=network,
            vm_id=vm_id,
            interface_name=interface_name
        )
        if allocated_ip:
            return allocated_ip

        raise ValueError(f"No available IP addresses in network {network_id}")

    async def _try_allocate_specific_ip(
        self,
        network: VPCNetwork,
        ip_address: str,
        vm_id: Optional[str],
        interface_name: Optional[str],
        ip_pool_id: Optional[str]
    ) -> Optional[NetworkIPAllocation]:
        """Try to allocate specific IP address."""
        # Validate IP is in network
        network_obj = ipaddress.ip_network(network.cidr, strict=False)
        ip_obj = ipaddress.ip_address(ip_address)

        if ip_obj not in network_obj:
            return None

        # Check if IP already allocated
        result = await self.db.execute(
            select(NetworkIPAllocation).where(
                and_(
                    NetworkIPAllocation.network_id == network.id,
                    NetworkIPAllocation.ip_address == ip_address,
                    NetworkIPAllocation.status == "allocated",
                    NetworkIPAllocation.deleted_at.is_(None)
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return None

        # Allocate IP
        allocation = NetworkIPAllocation(
            network_id=network.id,
            ip_pool_id=ip_pool_id,
            ip_address=ip_address,
            vm_id=vm_id,
            interface_name=interface_name,
            status="allocated"
        )

        self.db.add(allocation)
        await self.db.commit()
        await self.db.refresh(allocation)

        logger.info(f"Allocated specific IP {ip_address} to VM {vm_id}")
        return allocation

    async def _allocate_from_pool(
        self,
        network: VPCNetwork,
        pool_id: str,
        vm_id: Optional[str],
        interface_name: Optional[str]
    ) -> Optional[NetworkIPAllocation]:
        """Allocate next available IP from pool."""
        # Get pool
        result = await self.db.execute(
            select(NetworkIPPool).where(
                and_(
                    NetworkIPPool.id == pool_id,
                    NetworkIPPool.network_id == network.id,
                    NetworkIPPool.deleted_at.is_(None)
                )
            )
        )
        pool = result.scalar_one_or_none()
        if not pool:
            return None

        # Get all allocated IPs in pool range
        alloc_result = await self.db.execute(
            select(NetworkIPAllocation.ip_address).where(
                and_(
                    NetworkIPAllocation.network_id == network.id,
                    NetworkIPAllocation.status == "allocated",
                    NetworkIPAllocation.deleted_at.is_(None)
                )
            )
        )
        allocated_ips = {row[0] for row in alloc_result.all()}

        # Find first available IP in pool range
        start_ip = ipaddress.ip_address(pool.start_ip)
        end_ip = ipaddress.ip_address(pool.end_ip)

        current_ip = start_ip
        while current_ip <= end_ip:
            ip_str = str(current_ip)
            if ip_str not in allocated_ips:
                # Found available IP
                allocation = NetworkIPAllocation(
                    network_id=network.id,
                    ip_pool_id=pool.id,
                    ip_address=ip_str,
                    vm_id=vm_id,
                    interface_name=interface_name,
                    status="allocated"
                )

                self.db.add(allocation)
                await self.db.commit()
                await self.db.refresh(allocation)

                logger.info(f"Allocated IP {ip_str} from pool {pool.id} to VM {vm_id}")
                return allocation

            current_ip += 1

        # Pool exhausted
        return None

    async def _allocate_from_cidr(
        self,
        network: VPCNetwork,
        vm_id: Optional[str],
        interface_name: Optional[str]
    ) -> Optional[NetworkIPAllocation]:
        """Allocate from entire network CIDR (skip network, broadcast, gateway)."""
        network_obj = ipaddress.ip_network(network.cidr, strict=False)

        # Get all allocated IPs
        alloc_result = await self.db.execute(
            select(NetworkIPAllocation.ip_address).where(
                and_(
                    NetworkIPAllocation.network_id == network.id,
                    NetworkIPAllocation.status == "allocated",
                    NetworkIPAllocation.deleted_at.is_(None)
                )
            )
        )
        allocated_ips = {row[0] for row in alloc_result.all()}

        # Reserved IPs
        reserved = {str(network_obj.network_address), str(network_obj.broadcast_address)}
        if network.gateway:
            reserved.add(network.gateway)

        # Find first available
        for ip in network_obj.hosts():
            ip_str = str(ip)
            if ip_str not in allocated_ips and ip_str not in reserved:
                allocation = NetworkIPAllocation(
                    network_id=network.id,
                    ip_pool_id=None,  # Not from specific pool
                    ip_address=ip_str,
                    vm_id=vm_id,
                    interface_name=interface_name,
                    status="allocated"
                )

                self.db.add(allocation)
                await self.db.commit()
                await self.db.refresh(allocation)

                logger.info(f"Allocated IP {ip_str} from CIDR to VM {vm_id}")
                return allocation

        return None

    async def release_ip(
        self,
        allocation_id: str,
        organization_id: str
    ) -> bool:
        """Release IP allocation.

        Args:
            allocation_id: Allocation ID
            organization_id: Organization ID for authorization

        Returns:
            True if released, False if not found

        Example:
            >>> success = await ipam_service.release_ip("alloc-123", "org-456")
        """
        # Get allocation with network check
        result = await self.db.execute(
            select(NetworkIPAllocation)
            .join(VPCNetwork, NetworkIPAllocation.network_id == VPCNetwork.id)
            .where(
                and_(
                    NetworkIPAllocation.id == allocation_id,
                    VPCNetwork.organization_id == organization_id,
                    NetworkIPAllocation.deleted_at.is_(None)
                )
            )
        )
        allocation = result.scalar_one_or_none()
        if not allocation:
            return False

        allocation.status = "released"
        allocation.vm_id = None
        allocation.interface_name = None

        await self.db.commit()

        logger.info(f"Released IP allocation {allocation_id} ({allocation.ip_address})")
        return True

    async def list_allocations(
        self,
        network_id: str,
        organization_id: str,
        status: Optional[str] = None
    ) -> List[NetworkIPAllocation]:
        """List IP allocations in network.

        Args:
            network_id: Network ID
            organization_id: Organization ID for authorization
            status: Optional status filter (allocated, released, reserved)

        Returns:
            List of NetworkIPAllocation objects

        Example:
            >>> allocations = await ipam_service.list_allocations("net-123", "org-456")
        """
        # Verify network access
        result = await self.db.execute(
            select(VPCNetwork).where(
                and_(
                    VPCNetwork.id == network_id,
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
        )
        network = result.scalar_one_or_none()
        if not network:
            return []

        # Build query
        query = select(NetworkIPAllocation).where(
            and_(
                NetworkIPAllocation.network_id == network_id,
                NetworkIPAllocation.deleted_at.is_(None)
            )
        )

        if status:
            query = query.where(NetworkIPAllocation.status == status)

        query = query.order_by(NetworkIPAllocation.created_at)

        alloc_result = await self.db.execute(query)
        return list(alloc_result.scalars().all())
