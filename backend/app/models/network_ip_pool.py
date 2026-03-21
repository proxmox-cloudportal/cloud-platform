"""Network IP pool model for defining allocatable IP ranges."""
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.vpc_network import VPCNetwork
    from app.models.network_ip_allocation import NetworkIPAllocation


class NetworkIPPool(BaseModel):
    """IP address pool within a network."""

    __tablename__ = "network_ip_pools"

    # Pool configuration
    network_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vpc_networks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    pool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_ip: Mapped[str] = mapped_column(String(45), nullable=False)  # e.g., "10.100.0.10"
    end_ip: Mapped[str] = mapped_column(String(45), nullable=False)    # e.g., "10.100.0.250"

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    network: Mapped["VPCNetwork"] = relationship("VPCNetwork", back_populates="ip_pools", lazy="selectin")
    allocations: Mapped[List["NetworkIPAllocation"]] = relationship(
        "NetworkIPAllocation",
        back_populates="ip_pool",
        lazy="selectin"
    )
