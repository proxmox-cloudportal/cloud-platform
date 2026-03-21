"""VPC Network model for VLAN-based network isolation."""
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.vm_network_interface import VMNetworkInterface
    from app.models.network_ip_allocation import NetworkIPAllocation
    from app.models.network_ip_pool import NetworkIPPool


class VPCNetwork(BaseModel):
    """VPC Network with VLAN isolation."""

    __tablename__ = "vpc_networks"

    # Ownership
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Network configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # VLAN configuration
    vlan_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    bridge: Mapped[str] = mapped_column(String(50), nullable=False, default="vmbr0")

    # Subnet configuration
    cidr: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "10.100.0.0/24"
    gateway: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    dns_servers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Network settings
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Metadata
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin", foreign_keys=[created_by])
    interfaces: Mapped[List["VMNetworkInterface"]] = relationship(
        "VMNetworkInterface",
        back_populates="network",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    ip_allocations: Mapped[List["NetworkIPAllocation"]] = relationship(
        "NetworkIPAllocation",
        back_populates="network",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    ip_pools: Mapped[List["NetworkIPPool"]] = relationship(
        "NetworkIPPool",
        back_populates="network",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
