"""
Quota management and enforcement service.
"""
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.resource_quota import ResourceQuota
from app.models.virtual_machine import VirtualMachine
from app.models.proxmox_cluster import ProxmoxCluster
from app.models.vm_disk import VMDisk


@dataclass
class QuotaCheckResult:
    """Result of quota availability check."""
    is_available: bool
    exceeded_resources: List[str]
    current_usage: Dict[str, float]
    limits: Dict[str, float]
    remaining: Dict[str, float]


class QuotaService:
    """Service for quota management and enforcement."""

    # Resource type definitions
    RESOURCE_TYPES = {
        "cpu_cores": "CPU Cores",
        "memory_gb": "Memory (GB)",
        "storage_gb": "Storage (GB)",
        "vm_count": "VM Count",
        "cluster_count": "Cluster Count",
        "network_segments": "Network Segments"
    }

    # Default quota limits for new organizations
    DEFAULT_LIMITS = {
        "cpu_cores": 100.0,
        "memory_gb": 512.0,
        "storage_gb": 5000.0,
        "vm_count": 50.0,
        "cluster_count": 5.0,
        "network_segments": 10.0
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_quota(
        self,
        organization_id: str,
        resource_type: str,
        default_limit: float = None
    ) -> ResourceQuota:
        """
        Get existing quota or create with default limit.

        Args:
            organization_id: Organization UUID
            resource_type: Type of resource
            default_limit: Default limit if creating (uses DEFAULT_LIMITS if None)

        Returns:
            ResourceQuota object
        """
        result = await self.db.execute(
            select(ResourceQuota).where(
                ResourceQuota.organization_id == organization_id,
                ResourceQuota.resource_type == resource_type,
                ResourceQuota.deleted_at.is_(None)
            )
        )
        quota = result.scalar_one_or_none()

        if not quota:
            if default_limit is None:
                default_limit = self.DEFAULT_LIMITS.get(resource_type, 0.0)

            quota = ResourceQuota(
                organization_id=organization_id,
                resource_type=resource_type,
                limit_value=default_limit,
                used_value=0.0
            )
            self.db.add(quota)
            await self.db.commit()
            await self.db.refresh(quota)

        return quota

    async def check_quota_availability(
        self,
        organization_id: str,
        cpu_cores: int = 0,
        memory_gb: float = 0,
        storage_gb: float = 0,
        vm_count: int = 0,
        network_segments: int = 0
    ) -> QuotaCheckResult:
        """
        Check if requested resources are within quota limits.

        Args:
            organization_id: Organization UUID
            cpu_cores: Requested CPU cores
            memory_gb: Requested memory in GB
            storage_gb: Requested storage in GB
            vm_count: Requested VM count
            network_segments: Requested network segments

        Returns:
            QuotaCheckResult with availability status
        """
        requested = {
            "cpu_cores": float(cpu_cores),
            "memory_gb": memory_gb,
            "storage_gb": storage_gb,
            "vm_count": float(vm_count),
            "network_segments": float(network_segments)
        }

        exceeded = []
        current_usage = {}
        limits = {}
        remaining = {}

        for resource_type, requested_amount in requested.items():
            if requested_amount == 0:
                continue

            quota = await self.get_or_create_quota(
                organization_id=organization_id,
                resource_type=resource_type
            )

            current_usage[resource_type] = quota.used_value
            limits[resource_type] = quota.limit_value
            remaining[resource_type] = quota.remaining

            # Check if request would exceed limit
            if not quota.has_available_quota(requested_amount):
                exceeded.append(
                    f"{self.RESOURCE_TYPES[resource_type]}: "
                    f"requested {requested_amount}, "
                    f"available {quota.remaining}, "
                    f"limit {quota.limit_value}"
                )

        return QuotaCheckResult(
            is_available=len(exceeded) == 0,
            exceeded_resources=exceeded,
            current_usage=current_usage,
            limits=limits,
            remaining=remaining
        )

    async def increment_usage(
        self,
        organization_id: str,
        cpu_cores: int = 0,
        memory_gb: float = 0,
        storage_gb: float = 0,
        vm_count: int = 0,
        cluster_count: int = 0,
        network_segments: int = 0
    ):
        """
        Increment quota usage.

        Args:
            organization_id: Organization UUID
            cpu_cores: CPU cores to add
            memory_gb: Memory to add in GB
            storage_gb: Storage to add in GB
            vm_count: VM count to add
            cluster_count: Cluster count to add
            network_segments: Network segments to add
        """
        updates = {
            "cpu_cores": float(cpu_cores),
            "memory_gb": memory_gb,
            "storage_gb": storage_gb,
            "vm_count": float(vm_count),
            "cluster_count": float(cluster_count),
            "network_segments": float(network_segments)
        }

        for resource_type, amount in updates.items():
            if amount == 0:
                continue

            quota = await self.get_or_create_quota(
                organization_id=organization_id,
                resource_type=resource_type
            )

            quota.used_value += amount
            quota.last_calculated_at = datetime.utcnow()

        await self.db.commit()

    async def decrement_usage(
        self,
        organization_id: str,
        cpu_cores: int = 0,
        memory_gb: float = 0,
        storage_gb: float = 0,
        vm_count: int = 0,
        cluster_count: int = 0,
        network_segments: int = 0
    ):
        """
        Decrement quota usage.

        Args:
            organization_id: Organization UUID
            cpu_cores: CPU cores to remove
            memory_gb: Memory to remove in GB
            storage_gb: Storage to remove in GB
            vm_count: VM count to remove
            cluster_count: Cluster count to remove
            network_segments: Network segments to remove
        """
        updates = {
            "cpu_cores": float(cpu_cores),
            "memory_gb": memory_gb,
            "storage_gb": storage_gb,
            "vm_count": float(vm_count),
            "cluster_count": float(cluster_count),
            "network_segments": float(network_segments)
        }

        for resource_type, amount in updates.items():
            if amount == 0:
                continue

            quota = await self.get_or_create_quota(
                organization_id=organization_id,
                resource_type=resource_type
            )

            # Ensure usage doesn't go negative
            quota.used_value = max(0, quota.used_value - amount)
            quota.last_calculated_at = datetime.utcnow()

        await self.db.commit()

    async def recalculate_usage(self, organization_id: str):
        """
        Recalculate actual usage from database.

        Run periodically to fix drift between quota and actual usage.

        Args:
            organization_id: Organization UUID
        """
        # Calculate VM-based resources (CPU, memory, VM count)
        vm_result = await self.db.execute(
            select(
                func.count(VirtualMachine.id).label("vm_count"),
                func.sum(VirtualMachine.cpu_cores).label("total_cpu"),
                func.sum(VirtualMachine.memory_mb).label("total_memory")
            ).where(
                VirtualMachine.organization_id == organization_id,
                VirtualMachine.deleted_at.is_(None),
                VirtualMachine.status != "error"  # Don't count failed VMs
            )
        )
        vm_stats = vm_result.one()

        # Update VM-based quotas
        await self._update_quota_usage(
            organization_id, "vm_count", float(vm_stats.vm_count or 0)
        )
        await self._update_quota_usage(
            organization_id, "cpu_cores", float(vm_stats.total_cpu or 0)
        )
        await self._update_quota_usage(
            organization_id, "memory_gb", float(vm_stats.total_memory or 0) / 1024
        )

        # Calculate storage from vm_disks (sum all non-CDROM disks)
        storage_result = await self.db.execute(
            select(
                func.sum(VMDisk.size_gb).label("total_storage")
            ).join(
                VirtualMachine, VMDisk.vm_id == VirtualMachine.id
            ).where(
                VirtualMachine.organization_id == organization_id,
                VirtualMachine.deleted_at.is_(None),
                VMDisk.deleted_at.is_(None),
                VMDisk.is_cdrom == False,  # Don't count CD-ROM devices
                VirtualMachine.status != "error"  # Don't count failed VMs
            )
        )
        storage_stats = storage_result.one()

        await self._update_quota_usage(
            organization_id, "storage_gb", float(storage_stats.total_storage or 0)
        )

        # Calculate cluster count
        cluster_result = await self.db.execute(
            select(func.count(ProxmoxCluster.id)).where(
                ProxmoxCluster.organization_id == organization_id,
                ProxmoxCluster.deleted_at.is_(None)
            )
        )
        cluster_count = cluster_result.scalar_one()

        await self._update_quota_usage(
            organization_id, "cluster_count", float(cluster_count)
        )

        # Calculate network segments count
        from app.models.vpc_network import VPCNetwork
        network_result = await self.db.execute(
            select(func.count(VPCNetwork.id)).where(
                VPCNetwork.organization_id == organization_id,
                VPCNetwork.deleted_at.is_(None)
            )
        )
        network_count = network_result.scalar_one()

        await self._update_quota_usage(
            organization_id, "network_segments", float(network_count)
        )

        await self.db.commit()

    async def _update_quota_usage(
        self,
        organization_id: str,
        resource_type: str,
        used_value: float
    ):
        """
        Internal method to update quota usage.

        Args:
            organization_id: Organization UUID
            resource_type: Type of resource
            used_value: New usage value
        """
        quota = await self.get_or_create_quota(
            organization_id=organization_id,
            resource_type=resource_type
        )
        quota.used_value = used_value
        quota.last_calculated_at = datetime.utcnow()

    async def get_all_quotas(self, organization_id: str) -> List[ResourceQuota]:
        """
        Get all quotas for an organization.

        Ensures all resource types exist.

        Args:
            organization_id: Organization UUID

        Returns:
            List of ResourceQuota objects
        """
        # Ensure all resource types exist
        for resource_type in self.RESOURCE_TYPES.keys():
            await self.get_or_create_quota(
                organization_id=organization_id,
                resource_type=resource_type
            )

        # Fetch all quotas
        result = await self.db.execute(
            select(ResourceQuota).where(
                ResourceQuota.organization_id == organization_id,
                ResourceQuota.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())

    async def update_quota_limit(
        self,
        organization_id: str,
        resource_type: str,
        new_limit: float
    ) -> ResourceQuota:
        """
        Update quota limit for a resource type.

        Args:
            organization_id: Organization UUID
            resource_type: Type of resource
            new_limit: New limit value

        Returns:
            Updated ResourceQuota object
        """
        quota = await self.get_or_create_quota(
            organization_id=organization_id,
            resource_type=resource_type
        )

        quota.limit_value = new_limit
        await self.db.commit()
        await self.db.refresh(quota)

        return quota
