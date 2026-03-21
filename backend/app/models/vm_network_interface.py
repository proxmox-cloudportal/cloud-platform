"""VM network interface model for tracking VM network attachments."""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.virtual_machine import VirtualMachine
    from app.models.vpc_network import VPCNetwork
    from app.models.network_ip_allocation import NetworkIPAllocation


class VMNetworkInterface(BaseModel):
    """VM network interface for tracking network attachments with VLAN configuration."""

    __tablename__ = "vm_network_interfaces"

    # VM and network association
    vm_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("virtual_machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    network_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vpc_networks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Interface configuration
    interface_name: Mapped[str] = mapped_column(String(10), nullable=False)  # net0, net1, net2, net3
    mac_address: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    model: Mapped[str] = mapped_column(String(20), nullable=False, default="virtio")  # virtio, e1000, rtl8139

    # IP configuration
    ip_allocation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("network_ip_allocations.id", ondelete="SET NULL"),
        nullable=True
    )

    # Order/priority
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interface_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 0=net0, 1=net1, etc.

    # Proxmox configuration
    proxmox_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Full config string

    # Relationships
    vm: Mapped["VirtualMachine"] = relationship("VirtualMachine", back_populates="network_interfaces", lazy="selectin")
    network: Mapped["VPCNetwork"] = relationship("VPCNetwork", back_populates="interfaces", lazy="selectin")
    ip_allocation: Mapped[Optional["NetworkIPAllocation"]] = relationship("NetworkIPAllocation", lazy="selectin")
