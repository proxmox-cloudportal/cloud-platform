"""
Virtual Machine model for managing VMs across Proxmox clusters.
"""
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.vm_disk import VMDisk
    from app.models.vm_network_interface import VMNetworkInterface


class VirtualMachine(BaseModel):
    """Virtual Machine model."""

    __tablename__ = "virtual_machines"

    # Ownership
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # VM identification
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, default=list, nullable=True)

    # Proxmox details
    proxmox_cluster_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("proxmox_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    proxmox_node: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proxmox_vmid: Mapped[int] = mapped_column(Integer, nullable=False)

    # VM configuration
    os_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False)
    cpu_sockets: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    boot_order: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "ide2;scsi0"

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="provisioning",
        index=True
    )  # provisioning, running, stopped, paused, error
    power_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # on, off

    # Networking
    network_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vpc_networks.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # Primary network for VM provisioning
    primary_ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    mac_addresses: Mapped[Optional[dict]] = mapped_column(JSON, default=list, nullable=True)

    # Timestamps
    provisioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id], lazy="selectin")
    proxmox_cluster: Mapped["ProxmoxCluster"] = relationship(
        "ProxmoxCluster",
        foreign_keys=[proxmox_cluster_id],
        lazy="selectin"
    )
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        back_populates="virtual_machines",
        lazy="selectin"
    )
    disks: Mapped[list["VMDisk"]] = relationship(
        "VMDisk",
        back_populates="vm",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    network_interfaces: Mapped[list["VMNetworkInterface"]] = relationship(
        "VMNetworkInterface",
        back_populates="vm",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<VirtualMachine(id={self.id}, name={self.name}, status={self.status})>"
