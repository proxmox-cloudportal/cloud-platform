"""
Pydantic schemas for ISO Image API requests and responses.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# Request schemas
class ISOUploadMetadata(BaseModel):
    """Metadata for ISO upload."""

    name: str = Field(..., min_length=1, max_length=255, description="ISO filename")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name for UI")
    description: Optional[str] = Field(None, description="Description of the ISO")
    os_type: Optional[str] = Field(None, max_length=50, description="OS type (linux, windows, etc.)")
    os_version: Optional[str] = Field(None, max_length=100, description="OS version (e.g., 22.04, 11)")
    architecture: str = Field(default="x86_64", max_length=20, description="CPU architecture")
    is_public: bool = Field(default=False, description="Make ISO available to all organizations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "ubuntu-22.04.3-live-server-amd64.iso",
                "display_name": "Ubuntu 22.04 LTS Server",
                "description": "Ubuntu 22.04.3 LTS Server installation media",
                "os_type": "linux",
                "os_version": "22.04",
                "architecture": "x86_64",
                "is_public": True
            }
        }
    )


class ISOUploadFromURL(BaseModel):
    """Schema for uploading ISO from a URL."""

    url: str = Field(..., min_length=1, description="URL to download the ISO from")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name for UI")
    description: Optional[str] = Field(None, description="Description of the ISO")
    os_type: Optional[str] = Field(None, max_length=50, description="OS type (linux, windows, etc.)")
    os_version: Optional[str] = Field(None, max_length=100, description="OS version (e.g., 22.04, 11)")
    architecture: str = Field(default="x86_64", max_length=20, description="CPU architecture")
    is_public: bool = Field(default=False, description="Make ISO available to all organizations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso",
                "display_name": "Ubuntu 22.04 LTS Server",
                "description": "Ubuntu 22.04.3 LTS Server installation media",
                "os_type": "linux",
                "os_version": "22.04",
                "architecture": "x86_64",
                "is_public": True
            }
        }
    )


class ISOUpdate(BaseModel):
    """Schema for updating ISO metadata."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    os_type: Optional[str] = Field(None, max_length=50)
    os_version: Optional[str] = Field(None, max_length=100)
    is_public: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "display_name": "Ubuntu 22.04.4 LTS Server",
                "description": "Updated description",
                "is_public": False
            }
        }
    )


# Response schemas
class UploaderInfo(BaseModel):
    """Minimal uploader info for ISO response."""

    id: str
    username: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ISOProxmoxClusterInfo(BaseModel):
    """Minimal Proxmox cluster info for ISO response."""

    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class ISOResponse(BaseModel):
    """Schema for ISO image response."""

    id: str
    name: str
    display_name: str
    description: Optional[str]
    os_type: Optional[str]
    os_version: Optional[str]
    architecture: str

    # Ownership
    organization_id: Optional[str]
    is_public: bool
    uploader: UploaderInfo

    # File info
    filename: str
    file_size_bytes: int
    checksum_sha256: str

    # Storage
    storage_backend: str
    proxmox_cluster: Optional[ISOProxmoxClusterInfo]
    proxmox_storage: Optional[str]
    proxmox_volid: Optional[str]

    # Source
    source_url: Optional[str]
    source_type: str

    # Status
    upload_status: str
    upload_progress: float
    error_message: Optional[str]
    download_status: Optional[str]

    # Timestamps
    created_at: datetime
    uploaded_at: Optional[datetime]
    synced_to_proxmox_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ISOListResponse(BaseModel):
    """Schema for paginated ISO list response."""

    data: List[ISOResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ISOUploadInitResponse(BaseModel):
    """Schema for ISO upload initiation response."""

    id: str
    upload_url: Optional[str]
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "upload_url": None,
                "message": "ISO upload initiated. Processing in background."
            }
        }
    )
