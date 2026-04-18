"""
Pydantic schemas for Virtual Machine API requests and responses.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.vm_disk import DiskCreate, DiskResponse


# Base schema
class VMBase(BaseModel):
    """Base VM schema."""

    name: str = Field(..., min_length=1, max_length=255)
    hostname: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    cpu_cores: int = Field(..., ge=1, le=64)
    memory_mb: int = Field(..., ge=512, le=524288)  # 512MB to 512GB
    os_type: Optional[str] = Field(None, max_length=50)


# Request schemas
class VMCreate(BaseModel):
    """Schema for creating a new VM."""

    name: str = Field(..., min_length=1, max_length=255)
    hostname: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    # Resource configuration
    cpu_cores: int = Field(2, ge=1, le=64)
    cpu_sockets: int = Field(1, ge=1, le=4)
    memory_mb: int = Field(2048, ge=512, le=524288)

    # Disk configuration (legacy field for backward compatibility)
    disk_gb: Optional[int] = Field(None, ge=10, le=10240, description="DEPRECATED: Use disks[] instead")

    # Multi-disk configuration
    disks: List[DiskCreate] = Field(
        default_factory=lambda: [DiskCreate(size_gb=20, is_boot_disk=True)],
        description="List of disks to attach to the VM"
    )

    # ISO boot configuration
    iso_image_id: Optional[str] = Field(None, description="ISO image ID to mount for installation")
    boot_order: Optional[str] = Field(None, max_length=100, description="Boot order (e.g., 'disk,cdrom')")

    # Proxmox configuration
    proxmox_cluster_id: Optional[str] = None  # Auto-select if not provided
    os_type: Optional[str] = None

    # Network (optional for now)
    network_id: Optional[str] = None

    # Tags
    tags: Optional[List[str]] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "web-server-01",
                "hostname": "web01.example.com",
                "description": "Production web server",
                "cpu_cores": 4,
                "cpu_sockets": 1,
                "memory_mb": 8192,
                "disks": [
                    {
                        "size_gb": 40,
                        "storage_pool": "local-lvm",
                        "disk_interface": "scsi",
                        "is_boot_disk": True
                    },
                    {
                        "size_gb": 100,
                        "storage_pool": "ceph-storage",
                        "disk_interface": "scsi",
                        "is_boot_disk": False
                    }
                ],
                "iso_image_id": "550e8400-e29b-41d4-a716-446655440000",
                "boot_order": "cdrom,disk",
                "os_type": "linux",
                "tags": ["production", "web"]
            }
        }
    )


class VMUpdate(BaseModel):
    """Schema for updating VM configuration."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    hostname: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    cpu_cores: Optional[int] = Field(None, ge=1, le=64)
    memory_mb: Optional[int] = Field(None, ge=512, le=524288)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "web-server-01-updated",
                "description": "Updated production web server",
                "cpu_cores": 8,
                "memory_mb": 16384
            }
        }
    )


# Response schemas
class ProxmoxClusterInfo(BaseModel):
    """Minimal Proxmox cluster info for VM response."""

    id: str
    name: str
    region: Optional[str]
    datacenter: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class VMOwnerInfo(BaseModel):
    """Minimal owner info for VM response."""

    id: str
    username: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class VMResponse(BaseModel):
    """Schema for VM response."""

    id: str
    name: str
    hostname: Optional[str]
    description: Optional[str]

    # Status
    status: str
    power_state: Optional[str]

    # Resources
    cpu_cores: int
    cpu_sockets: int
    memory_mb: int

    # Disks
    disks: Optional[List[DiskResponse]] = Field(default_factory=list, description="List of attached disks")
    boot_order: Optional[str]

    # Proxmox
    vm_type: str
    proxmox_vmid: int
    proxmox_node: Optional[str]
    proxmox_cluster: ProxmoxClusterInfo

    # Network
    primary_ip_address: Optional[str]

    # Owner
    owner: VMOwnerInfo

    # Metadata
    os_type: Optional[str]
    tags: Optional[List]

    # Timestamps
    created_at: datetime
    provisioned_at: Optional[datetime]
    started_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class VMListResponse(BaseModel):
    """Schema for paginated VM list response."""

    data: List[VMResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class VMActionRequest(BaseModel):
    """Schema for VM actions (start, stop, restart)."""

    force: bool = Field(default=False, description="Force the action")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "force": False
            }
        }
    )


class VMStatsResponse(BaseModel):
    """Schema for VM performance statistics."""

    cpu_usage_percent: float
    memory_usage_percent: float
    memory_used_mb: int
    disk_read_mb: float
    disk_write_mb: float
    network_in_mb: float
    network_out_mb: float
    uptime_seconds: Optional[int]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cpu_usage_percent": 15.3,
                "memory_usage_percent": 45.2,
                "memory_used_mb": 3686,
                "disk_read_mb": 125.5,
                "disk_write_mb": 89.2,
                "network_in_mb": 1245.8,
                "network_out_mb": 987.3,
                "uptime_seconds": 86400
            }
        }
    )


class VMResize(BaseModel):
    """Schema for resizing VM CPU and memory."""

    cpu_cores: Optional[int] = Field(None, ge=1, le=128, description="Number of CPU cores")
    cpu_sockets: Optional[int] = Field(None, ge=1, le=4, description="Number of CPU sockets")
    memory_mb: Optional[int] = Field(None, ge=512, le=524288, description="Memory in MB (512MB - 512GB)")
