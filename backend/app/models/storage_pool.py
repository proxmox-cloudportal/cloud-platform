"""
Storage Pool model for tracking Proxmox storage pools.
"""
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import String, BigInteger, Boolean, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.proxmox_cluster import ProxmoxCluster


class StoragePool(BaseModel):
    """Storage pool model for Proxmox storage management."""

    __tablename__ = "storage_pools"

    # Proxmox Association
    proxmox_cluster_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("proxmox_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    storage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # lvm, lvmthin, zfs, ceph, nfs, dir

    # Capabilities
    content_types: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list
    )  # ["images", "iso", "backup", "rootdir", "vztmpl"]

    # Capacity
    total_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    used_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    available_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Sync
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    proxmox_cluster: Mapped["ProxmoxCluster"] = relationship(
        "ProxmoxCluster",
        lazy="selectin"
    )

    # Unique constraint: one storage name per cluster
    __table_args__ = (
        UniqueConstraint('proxmox_cluster_id', 'storage_name', name='uq_cluster_storage'),
    )

    @property
    def usage_percent(self) -> Optional[float]:
        """Calculate storage usage percentage."""
        if self.total_bytes and self.total_bytes > 0:
            return (self.used_bytes or 0) / self.total_bytes * 100
        return None

    def __repr__(self) -> str:
        return f"<StoragePool(id={self.id}, name={self.storage_name}, type={self.storage_type})>"
