"""
ISO Image model for storing and managing ISO files.
"""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, BigInteger, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.proxmox_cluster import ProxmoxCluster


class ISOImage(BaseModel):
    """ISO image model for managing installation media."""

    __tablename__ = "iso_images"

    # Ownership
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    uploaded_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ISO Metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    os_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    architecture: Mapped[str] = mapped_column(String(20), default="x86_64", nullable=False)

    # File Information
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # Storage Location
    storage_backend: Mapped[str] = mapped_column(String(50), default="local", nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proxmox_cluster_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("proxmox_clusters.id", ondelete="SET NULL"),
        nullable=True
    )
    proxmox_storage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proxmox_volid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Source Information
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(20), default="upload", nullable=False)  # upload, url

    # Upload Status
    upload_status: Mapped[str] = mapped_column(
        String(50),
        default="uploading",
        nullable=False,
        index=True
    )  # uploading, processing, ready, failed
    upload_progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Download Status (for URL uploads)
    download_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # downloading, downloaded, failed

    # Timestamps
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    synced_to_proxmox_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        lazy="selectin"
    )
    uploader: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[uploaded_by]
    )
    proxmox_cluster: Mapped[Optional["ProxmoxCluster"]] = relationship(
        "ProxmoxCluster",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ISOImage(id={self.id}, name={self.display_name}, status={self.upload_status})>"
