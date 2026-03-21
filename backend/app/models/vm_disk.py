"""
VM Disk model for tracking multiple disks per virtual machine.
"""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.virtual_machine import VirtualMachine
    from app.models.iso_image import ISOImage


class VMDisk(BaseModel):
    """VM disk model for tracking disk configuration."""

    __tablename__ = "vm_disks"

    # VM Association
    vm_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("virtual_machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Disk Configuration
    disk_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0, 1, 2...
    disk_interface: Mapped[str] = mapped_column(String(20), nullable=False)  # scsi, ide, virtio, sata
    disk_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Interface-specific number

    # Storage
    storage_pool: Mapped[str] = mapped_column(String(100), nullable=False)
    size_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # raw, qcow2

    # Disk Type
    is_boot_disk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_cdrom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ISO Mount (for CD-ROM)
    iso_image_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("iso_images.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Proxmox Details
    proxmox_disk_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default="creating",
        nullable=False
    )  # creating, ready, error, deleting

    # Timestamps
    attached_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    vm: Mapped["VirtualMachine"] = relationship(
        "VirtualMachine",
        back_populates="disks",
        lazy="selectin"
    )
    iso_image: Mapped[Optional["ISOImage"]] = relationship(
        "ISOImage",
        lazy="selectin"
    )

    # Unique constraint: one disk interface + number per VM
    __table_args__ = (
        UniqueConstraint('vm_id', 'disk_interface', 'disk_number', name='uq_vm_disk_interface'),
    )

    def __repr__(self) -> str:
        disk_name = f"{self.disk_interface}{self.disk_number}"
        return f"<VMDisk(id={self.id}, vm_id={self.vm_id}, disk={disk_name}, size={self.size_gb}GB)>"
