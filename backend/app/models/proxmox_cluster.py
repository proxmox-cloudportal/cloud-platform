"""
Proxmox cluster model for managing multiple Proxmox VE clusters.
"""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.organization import Organization


class ProxmoxCluster(BaseModel):
    """Proxmox cluster model for connecting to Proxmox VE."""

    __tablename__ = "proxmox_clusters"

    # Organization ownership (NULL = shared across all orgs)
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    is_shared: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    datacenter: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # API connection details
    api_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_username: Mapped[str] = mapped_column(String(100), nullable=False)
    api_password_encrypted: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    api_token_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_token_secret_encrypted: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Resource tracking
    total_cpu_cores: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_memory_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_storage_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Load balancing
    load_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Sync tracking
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ProxmoxCluster(id={self.id}, name={self.name}, region={self.region})>"
