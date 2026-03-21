"""VLAN pool management service for network isolation."""
from typing import Optional
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.vlan_pool import VLANPool

logger = logging.getLogger(__name__)


class VLANService:
    """Service for managing VLAN pool allocation and release."""

    MIN_VLAN = 100  # Reserve 1-99 for infrastructure
    MAX_VLAN = 4094  # IEEE 802.1Q max VLAN ID

    def __init__(self, db: AsyncSession):
        """Initialize VLAN service.

        Args:
            db: Database session
        """
        self.db = db

    async def initialize_vlan_pool(self) -> int:
        """Initialize VLAN pool with VLANs 100-4094.

        Creates 3,995 VLAN entries in the pool if they don't already exist.
        Safe to run multiple times - will skip existing VLANs.

        Returns:
            Number of VLANs created

        Example:
            >>> vlan_service = VLANService(db)
            >>> count = await vlan_service.initialize_vlan_pool()
            >>> print(f"Created {count} VLANs")
        """
        created_count = 0

        # Check if pool already initialized
        result = await self.db.execute(
            select(func.count(VLANPool.id))
        )
        existing_count = result.scalar()

        if existing_count > 0:
            logger.info(f"VLAN pool already initialized with {existing_count} entries")
            return 0

        logger.info(f"Initializing VLAN pool with VLANs {self.MIN_VLAN}-{self.MAX_VLAN}")

        # Create VLAN pool entries
        vlan_entries = []
        for vlan_id in range(self.MIN_VLAN, self.MAX_VLAN + 1):
            vlan_entry = VLANPool(
                vlan_id=vlan_id,
                status="available"
            )
            vlan_entries.append(vlan_entry)
            created_count += 1

            # Batch insert every 500 entries for performance
            if len(vlan_entries) >= 500:
                self.db.add_all(vlan_entries)
                await self.db.flush()
                vlan_entries = []

        # Insert remaining entries
        if vlan_entries:
            self.db.add_all(vlan_entries)

        await self.db.commit()
        logger.info(f"Successfully initialized {created_count} VLANs in pool")
        return created_count

    async def allocate_vlan(self, network_id: Optional[str]) -> int:
        """Allocate next available VLAN from pool.

        Uses sequential allocation starting from VLAN 100.
        Thread-safe via database row locking.

        Args:
            network_id: Network ID to allocate VLAN for (None if network not yet created)

        Returns:
            Allocated VLAN ID

        Raises:
            RuntimeError: If no VLANs available in pool

        Example:
            >>> vlan_id = await vlan_service.allocate_vlan("network-123")
            >>> print(f"Allocated VLAN {vlan_id}")
        """
        # Find first available VLAN with row-level lock
        result = await self.db.execute(
            select(VLANPool)
            .where(VLANPool.status == "available")
            .order_by(VLANPool.vlan_id)
            .limit(1)
            .with_for_update()  # Row-level lock for thread safety
        )
        vlan_entry = result.scalar_one_or_none()

        if not vlan_entry:
            # Check total pool size for better error message
            total_result = await self.db.execute(
                select(func.count(VLANPool.id))
            )
            total_vlans = total_result.scalar()

            if total_vlans == 0:
                raise RuntimeError(
                    "VLAN pool not initialized. Run initialize_vlan_pool() first."
                )
            else:
                raise RuntimeError(
                    f"No available VLANs in pool. All {total_vlans} VLANs are allocated."
                )

        # Mark as allocated
        vlan_entry.status = "allocated"
        vlan_entry.allocated_to_network_id = network_id
        vlan_entry.allocated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(vlan_entry)

        logger.info(f"Allocated VLAN {vlan_entry.vlan_id} to network {network_id}")
        return vlan_entry.vlan_id

    async def release_vlan(self, vlan_id: int) -> None:
        """Release VLAN back to available pool.

        Args:
            vlan_id: VLAN ID to release

        Raises:
            ValueError: If VLAN not found in pool

        Example:
            >>> await vlan_service.release_vlan(100)
        """
        result = await self.db.execute(
            select(VLANPool).where(VLANPool.vlan_id == vlan_id)
        )
        vlan_entry = result.scalar_one_or_none()

        if not vlan_entry:
            raise ValueError(f"VLAN {vlan_id} not found in pool")

        previous_network_id = vlan_entry.allocated_to_network_id

        # Mark as available
        vlan_entry.status = "available"
        vlan_entry.allocated_to_network_id = None
        vlan_entry.allocated_at = None

        await self.db.commit()

        logger.info(
            f"Released VLAN {vlan_id} (was allocated to network {previous_network_id})"
        )

    async def update_allocation(self, vlan_id: int, network_id: str) -> None:
        """Update VLAN allocation to associate with network.

        Used after network creation to link VLAN to network ID.

        Args:
            vlan_id: VLAN ID to update
            network_id: Network ID to associate with

        Raises:
            ValueError: If VLAN not found or not allocated

        Example:
            >>> await vlan_service.update_allocation(100, "network-123")
        """
        result = await self.db.execute(
            select(VLANPool).where(VLANPool.vlan_id == vlan_id)
        )
        vlan_entry = result.scalar_one_or_none()

        if not vlan_entry:
            raise ValueError(f"VLAN {vlan_id} not found in pool")

        if vlan_entry.status != "allocated":
            raise ValueError(f"VLAN {vlan_id} is not allocated (status: {vlan_entry.status})")

        vlan_entry.allocated_to_network_id = network_id

        await self.db.commit()

        logger.debug(f"Updated VLAN {vlan_id} allocation to network {network_id}")

    async def get_available_vlan_count(self) -> int:
        """Get count of available VLANs in pool.

        Returns:
            Number of available VLANs

        Example:
            >>> count = await vlan_service.get_available_vlan_count()
            >>> print(f"{count} VLANs available")
        """
        result = await self.db.execute(
            select(func.count(VLANPool.id))
            .where(VLANPool.status == "available")
        )
        return result.scalar() or 0

    async def get_vlan_status(self, vlan_id: int) -> Optional[VLANPool]:
        """Get VLAN pool entry by VLAN ID.

        Args:
            vlan_id: VLAN ID to look up

        Returns:
            VLANPool entry or None if not found

        Example:
            >>> vlan_status = await vlan_service.get_vlan_status(100)
            >>> if vlan_status:
            >>>     print(f"VLAN 100 status: {vlan_status.status}")
        """
        result = await self.db.execute(
            select(VLANPool).where(VLANPool.vlan_id == vlan_id)
        )
        return result.scalar_one_or_none()

    async def get_pool_stats(self) -> dict:
        """Get VLAN pool statistics.

        Returns:
            Dictionary with pool statistics including total, available, allocated counts

        Example:
            >>> stats = await vlan_service.get_pool_stats()
            >>> print(f"Available: {stats['available']}/{stats['total']}")
        """
        # Get counts by status
        result = await self.db.execute(
            select(
                VLANPool.status,
                func.count(VLANPool.id)
            ).group_by(VLANPool.status)
        )
        status_counts = dict(result.all())

        total_vlans = sum(status_counts.values())
        available = status_counts.get("available", 0)
        allocated = status_counts.get("allocated", 0)
        reserved = status_counts.get("reserved", 0)

        return {
            "total": total_vlans,
            "available": available,
            "allocated": allocated,
            "reserved": reserved,
            "utilization_percent": (allocated / total_vlans * 100) if total_vlans > 0 else 0,
            "vlan_range": f"{self.MIN_VLAN}-{self.MAX_VLAN}"
        }
