"""Network management service for VPC networking with VLAN isolation."""
from typing import Optional, List
import ipaddress
import logging
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vpc_network import VPCNetwork
from app.models.network_ip_pool import NetworkIPPool
from app.models.network_ip_allocation import NetworkIPAllocation
from app.services.vlan_service import VLANService
from app.services.quota_service import QuotaService
from app.schemas.network import NetworkCreate, NetworkUpdate

logger = logging.getLogger(__name__)


class NetworkService:
    """Service for managing VPC networks with VLAN allocation."""

    def __init__(self, db: AsyncSession):
        """Initialize network service.

        Args:
            db: Database session
        """
        self.db = db
        self.vlan_service = VLANService(db)
        self.quota_service = QuotaService(db)

    async def create_network(
        self,
        organization_id: str,
        created_by: str,
        network_data: NetworkCreate
    ) -> VPCNetwork:
        """Create VPC network with VLAN allocation.

        Args:
            organization_id: Organization ID
            created_by: User ID creating the network
            network_data: Network creation data

        Returns:
            Created VPCNetwork

        Raises:
            ValueError: If quota exceeded or CIDR invalid
            RuntimeError: If VLAN allocation fails

        Example:
            >>> network = await network_service.create_network(
            ...     organization_id="org-123",
            ...     created_by="user-456",
            ...     network_data=NetworkCreate(
            ...         name="Production",
            ...         cidr="10.100.0.0/24",
            ...         gateway="10.100.0.1"
            ...     )
            ... )
        """
        # 1. Validate CIDR notation
        try:
            ip_network = ipaddress.ip_network(network_data.cidr, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid CIDR notation: {e}")

        # 2. Check quota availability
        quota_check = await self.quota_service.check_quota_availability(
            organization_id=organization_id,
            network_segments=1
        )

        if not quota_check.is_available:
            raise ValueError(
                f"Network quota exceeded. {', '.join(quota_check.exceeded_resources)}"
            )

        # 3. Allocate VLAN (with None for network_id since network doesn't exist yet)
        vlan_id = await self.vlan_service.allocate_vlan(None)
        logger.info(f"Allocated VLAN {vlan_id} for network creation")

        try:
            # 4. Auto-generate gateway if not provided (use first usable IP)
            gateway = network_data.gateway
            if not gateway and ip_network.num_addresses > 2:
                # For /24: 10.100.0.1 (skip network address 10.100.0.0)
                gateway = str(list(ip_network.hosts())[0])
                logger.debug(f"Auto-generated gateway: {gateway}")

            # 5. Create network record
            network = VPCNetwork(
                organization_id=organization_id,
                created_by=created_by,
                name=network_data.name,
                description=network_data.description,
                vlan_id=vlan_id,
                bridge=network_data.bridge,
                cidr=network_data.cidr,
                gateway=gateway,
                dns_servers=network_data.dns_servers,
                is_shared=network_data.is_shared,
                is_default=False,  # Must be explicitly set via separate endpoint
                tags={}
            )

            self.db.add(network)
            await self.db.flush()  # Get network.id

            # 6. Update VLAN allocation with network ID
            await self.vlan_service.update_allocation(vlan_id, network.id)

            # 7. Increment quota usage
            await self.quota_service.increment_usage(
                organization_id=organization_id,
                network_segments=1
            )

            await self.db.commit()
            await self.db.refresh(network)

            logger.info(
                f"Created network {network.id} ({network.name}) "
                f"with VLAN {vlan_id} for org {organization_id}"
            )

            return network

        except Exception as e:
            # Rollback VLAN allocation on failure
            logger.error(f"Network creation failed, releasing VLAN {vlan_id}: {e}")
            await self.vlan_service.release_vlan(vlan_id)
            raise

    async def get_network(
        self,
        network_id: str,
        organization_id: str
    ) -> Optional[VPCNetwork]:
        """Get network by ID with organization scope.

        Args:
            network_id: Network ID
            organization_id: Organization ID for authorization

        Returns:
            VPCNetwork or None if not found

        Example:
            >>> network = await network_service.get_network("net-123", "org-456")
        """
        result = await self.db.execute(
            select(VPCNetwork).where(
                and_(
                    VPCNetwork.id == network_id,
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_networks(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[VPCNetwork]:
        """List networks in organization.

        Args:
            organization_id: Organization ID
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            List of VPCNetwork objects

        Example:
            >>> networks = await network_service.list_networks("org-123")
        """
        result = await self.db.execute(
            select(VPCNetwork)
            .where(
                and_(
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
            .order_by(VPCNetwork.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_networks(self, organization_id: str) -> int:
        """Count networks in organization.

        Args:
            organization_id: Organization ID

        Returns:
            Network count

        Example:
            >>> count = await network_service.count_networks("org-123")
        """
        result = await self.db.execute(
            select(func.count(VPCNetwork.id)).where(
                and_(
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
        )
        return result.scalar() or 0

    async def update_network(
        self,
        network_id: str,
        organization_id: str,
        update_data: NetworkUpdate
    ) -> Optional[VPCNetwork]:
        """Update network configuration.

        Note: CIDR and VLAN cannot be changed after creation.

        Args:
            network_id: Network ID
            organization_id: Organization ID for authorization
            update_data: Update data

        Returns:
            Updated VPCNetwork or None if not found

        Example:
            >>> network = await network_service.update_network(
            ...     "net-123",
            ...     "org-456",
            ...     NetworkUpdate(name="Updated Name")
            ... )
        """
        network = await self.get_network(network_id, organization_id)
        if not network:
            return None

        # Update allowed fields
        update_dict = update_data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            setattr(network, field, value)

        await self.db.commit()
        await self.db.refresh(network)

        logger.info(f"Updated network {network_id}: {list(update_dict.keys())}")
        return network

    async def delete_network(
        self,
        network_id: str,
        organization_id: str
    ) -> bool:
        """Delete network and release VLAN.

        Args:
            network_id: Network ID
            organization_id: Organization ID for authorization

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If network still has attached VMs

        Example:
            >>> success = await network_service.delete_network("net-123", "org-456")
        """
        network = await self.get_network(network_id, organization_id)
        if not network:
            return False

        # Check if network has attached interfaces
        from app.models.vm_network_interface import VMNetworkInterface
        result = await self.db.execute(
            select(func.count(VMNetworkInterface.id)).where(
                and_(
                    VMNetworkInterface.network_id == network_id,
                    VMNetworkInterface.deleted_at.is_(None)
                )
            )
        )
        interface_count = result.scalar() or 0

        if interface_count > 0:
            raise ValueError(
                f"Cannot delete network: {interface_count} VM(s) still attached. "
                "Detach all VMs first."
            )

        # Soft delete network
        from datetime import datetime
        network.deleted_at = datetime.utcnow()

        # Release VLAN back to pool
        await self.vlan_service.release_vlan(network.vlan_id)

        # Decrement quota
        await self.quota_service.decrement_usage(
            organization_id=organization_id,
            network_segments=1
        )

        await self.db.commit()

        logger.info(
            f"Deleted network {network_id} and released VLAN {network.vlan_id}"
        )
        return True

    async def set_default_network(
        self,
        network_id: str,
        organization_id: str
    ) -> VPCNetwork:
        """Set network as default for organization.

        Only one network can be default per organization.

        Args:
            network_id: Network ID to set as default
            organization_id: Organization ID

        Returns:
            Updated VPCNetwork

        Raises:
            ValueError: If network not found

        Example:
            >>> network = await network_service.set_default_network(
            ...     "net-123",
            ...     "org-456"
            ... )
        """
        network = await self.get_network(network_id, organization_id)
        if not network:
            raise ValueError(f"Network {network_id} not found")

        # Unset all other default networks in org
        result = await self.db.execute(
            select(VPCNetwork).where(
                and_(
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.is_default == True,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
        )
        for other_network in result.scalars().all():
            other_network.is_default = False

        # Set this network as default
        network.is_default = True

        await self.db.commit()
        await self.db.refresh(network)

        logger.info(f"Set network {network_id} as default for org {organization_id}")
        return network

    async def get_default_network(
        self,
        organization_id: str
    ) -> Optional[VPCNetwork]:
        """Get default network for organization.

        Args:
            organization_id: Organization ID

        Returns:
            Default VPCNetwork or None if no default set

        Example:
            >>> network = await network_service.get_default_network("org-123")
        """
        result = await self.db.execute(
            select(VPCNetwork).where(
                and_(
                    VPCNetwork.organization_id == organization_id,
                    VPCNetwork.is_default == True,
                    VPCNetwork.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_network_stats(
        self,
        network_id: str,
        organization_id: str
    ) -> dict:
        """Get network statistics (IP usage, VM count, etc.).

        Args:
            network_id: Network ID
            organization_id: Organization ID for authorization

        Returns:
            Dictionary with network statistics

        Example:
            >>> stats = await network_service.get_network_stats("net-123", "org-456")
            >>> print(f"VMs attached: {stats['vm_count']}")
        """
        network = await self.get_network(network_id, organization_id)
        if not network:
            return {}

        # Count IP allocations
        ip_alloc_result = await self.db.execute(
            select(func.count(NetworkIPAllocation.id)).where(
                and_(
                    NetworkIPAllocation.network_id == network_id,
                    NetworkIPAllocation.deleted_at.is_(None)
                )
            )
        )
        ip_allocation_count = ip_alloc_result.scalar() or 0

        # Count IP pools
        ip_pool_result = await self.db.execute(
            select(func.count(NetworkIPPool.id)).where(
                and_(
                    NetworkIPPool.network_id == network_id,
                    NetworkIPPool.deleted_at.is_(None)
                )
            )
        )
        ip_pool_count = ip_pool_result.scalar() or 0

        # Count attached VMs
        from app.models.vm_network_interface import VMNetworkInterface
        vm_result = await self.db.execute(
            select(func.count(func.distinct(VMNetworkInterface.vm_id))).where(
                and_(
                    VMNetworkInterface.network_id == network_id,
                    VMNetworkInterface.deleted_at.is_(None)
                )
            )
        )
        vm_count = vm_result.scalar() or 0

        # Calculate total IPs in network
        try:
            ip_network = ipaddress.ip_network(network.cidr, strict=False)
            total_ips = ip_network.num_addresses - 2  # Exclude network and broadcast
        except ValueError:
            total_ips = 0

        return {
            "network_id": network.id,
            "vlan_id": network.vlan_id,
            "cidr": network.cidr,
            "total_ips": total_ips,
            "allocated_ips": ip_allocation_count,
            "available_ips": max(0, total_ips - ip_allocation_count),
            "ip_pool_count": ip_pool_count,
            "vm_count": vm_count
        }
