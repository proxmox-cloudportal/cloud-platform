"""
Pydantic schemas for Storage Pool API requests and responses.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# Response schemas
class StoragePoolResponse(BaseModel):
    """Schema for storage pool response."""

    id: str
    proxmox_cluster_id: str
    storage_name: str
    storage_type: str

    # Capabilities
    content_types: List[str]

    # Capacity
    total_bytes: Optional[int]
    used_bytes: Optional[int]
    available_bytes: Optional[int]
    usage_percent: Optional[float]

    # Status
    is_active: bool
    is_shared: bool

    # Sync
    last_synced_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StoragePoolListResponse(BaseModel):
    """Schema for storage pool list response."""

    data: List[StoragePoolResponse]
    total: int


class StoragePoolSyncResponse(BaseModel):
    """Schema for storage pool sync response."""

    synced_pools: int
    added: int
    updated: int
    deactivated: int
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "synced_pools": 5,
                "added": 1,
                "updated": 3,
                "deactivated": 0,
                "message": "Successfully synced 5 storage pools from Proxmox cluster"
            }
        }
    )


class StoragePoolCapabilities(BaseModel):
    """Schema for storage pool capabilities."""

    supports_vm_images: bool
    supports_iso: bool
    supports_backups: bool
    supports_containers: bool

    @classmethod
    def from_content_types(cls, content_types: List[str]) -> "StoragePoolCapabilities":
        """Create capabilities from content_types list."""
        return cls(
            supports_vm_images="images" in content_types or "rootdir" in content_types,
            supports_iso="iso" in content_types,
            supports_backups="backup" in content_types,
            supports_containers="rootdir" in content_types or "vztmpl" in content_types
        )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supports_vm_images": True,
                "supports_iso": True,
                "supports_backups": True,
                "supports_containers": False
            }
        }
    )
