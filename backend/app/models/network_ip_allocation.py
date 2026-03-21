"""Network IP allocation model for tracking IP address assignments."""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.vpc_network import VPCNetwork
    from app.models.network_ip_pool import NetworkIPPool
    from app.models.virtual_machine import VirtualMachine


class NetworkIPAllocation(BaseModel):
    """IP address allocation tracking within networks."""

    __tablename__ = "network_ip_allocations"

    # Allocation details
    network_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vpc_networks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    ip_pool_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("network_ip_pools.id", ondelete="SET NULL"),
        nullable=True
    )  # NULL if manually assigned outside pool
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)

    # Assignment
    vm_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("virtual_machines.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    interface_name: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # net0, net1, net2, net3

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="allocated",
        index=True
    )  # allocated, released, reserved

    # Metadata
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    network: Mapped["VPCNetwork"] = relationship("VPCNetwork", back_populates="ip_allocations", lazy="selectin")
    ip_pool: Mapped[Optional["NetworkIPPool"]] = relationship("NetworkIPPool", back_populates="allocations", lazy="selectin")
    vm: Mapped[Optional["VirtualMachine"]] = relationship("VirtualMachine", lazy="selectin")
