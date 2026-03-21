"""
Pydantic schemas for VM Disk API requests and responses.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator


# Request schemas
class DiskCreate(BaseModel):
    """Schema for creating a disk during VM creation."""

    size_gb: int = Field(..., ge=1, le=10240, description="Disk size in GB (1GB to 10TB)")
    storage_pool: Optional[str] = Field(None, max_length=100, description="Storage pool name (auto-select if not provided)")
    disk_interface: str = Field(default="scsi", description="Disk interface type")
    disk_format: Optional[str] = Field(default="raw", max_length=20, description="Disk format (raw, qcow2)")
    is_boot_disk: bool = Field(default=False, description="Mark as boot disk")

    @field_validator('disk_interface')
    @classmethod
    def validate_disk_interface(cls, v: str) -> str:
        """Validate disk interface."""
        allowed = ['scsi', 'ide', 'virtio', 'sata']
        if v.lower() not in allowed:
            raise ValueError(f"disk_interface must be one of: {', '.join(allowed)}")
        return v.lower()

    @field_validator('disk_format')
    @classmethod
    def validate_disk_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate disk format."""
        if v is None:
            return v
        allowed = ['raw', 'qcow2']
        if v.lower() not in allowed:
            raise ValueError(f"disk_format must be one of: {', '.join(allowed)}")
        return v.lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "size_gb": 40,
                "storage_pool": "local-lvm",
                "disk_interface": "scsi",
                "disk_format": "raw",
                "is_boot_disk": True
            }
        }
    )


class DiskAttach(BaseModel):
    """Schema for attaching a disk to an existing VM."""

    size_gb: int = Field(..., ge=1, le=10240, description="Disk size in GB")
    storage_pool: str = Field(..., max_length=100, description="Storage pool name")
    disk_interface: str = Field(default="scsi", description="Disk interface type")
    disk_format: Optional[str] = Field(default="raw", max_length=20, description="Disk format")

    @field_validator('disk_interface')
    @classmethod
    def validate_disk_interface(cls, v: str) -> str:
        """Validate disk interface."""
        allowed = ['scsi', 'ide', 'virtio', 'sata']
        if v.lower() not in allowed:
            raise ValueError(f"disk_interface must be one of: {', '.join(allowed)}")
        return v.lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "size_gb": 100,
                "storage_pool": "ceph-storage",
                "disk_interface": "scsi",
                "disk_format": "raw"
            }
        }
    )


class DiskResize(BaseModel):
    """Schema for resizing a disk."""

    new_size_gb: int = Field(..., ge=1, le=10240, description="New disk size in GB (must be larger than current)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_size_gb": 80
            }
        }
    )


class DiskAttachISO(BaseModel):
    """Schema for attaching an ISO to a VM as CD-ROM."""

    iso_image_id: str = Field(..., description="ISO image ID to mount")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "iso_image_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )


# Response schemas
class ISOImageInfo(BaseModel):
    """Minimal ISO image info for disk response."""

    id: str
    name: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class DiskResponse(BaseModel):
    """Schema for disk response."""

    id: str
    vm_id: str
    disk_index: int
    disk_interface: str
    disk_number: int

    # Storage
    storage_pool: str
    size_gb: int
    disk_format: Optional[str]

    # Disk type
    is_boot_disk: bool
    is_cdrom: bool

    # ISO mount
    iso_image: Optional[ISOImageInfo]

    # Status
    status: str
    proxmox_disk_id: Optional[str]

    # Timestamps
    created_at: datetime
    attached_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class DiskListResponse(BaseModel):
    """Schema for disk list response."""

    data: List[DiskResponse]
    total: int
