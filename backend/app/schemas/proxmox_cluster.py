"""
Pydantic schemas for Proxmox Cluster operations.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class ProxmoxClusterBase(BaseModel):
    """Base schema for Proxmox Cluster"""
    name: str = Field(..., min_length=1, max_length=255, description="Cluster name")
    datacenter: Optional[str] = Field(None, max_length=100, description="Datacenter location")
    region: Optional[str] = Field(None, max_length=100, description="Region")
    api_url: str = Field(..., description="Proxmox API URL (e.g., https://proxmox.example.com:8006)")
    api_username: str = Field(..., description="API username (e.g., root@pam)")
    verify_ssl: bool = Field(True, description="Verify SSL certificate")
    is_active: bool = Field(True, description="Is cluster active")


class ProxmoxClusterCreate(ProxmoxClusterBase):
    """Schema for creating a new Proxmox Cluster"""
    # API authentication options
    api_token_id: Optional[str] = Field(None, description="API token ID")
    api_token_secret: Optional[str] = Field(None, description="API token secret")
    api_password: Optional[str] = Field(None, description="API password (alternative to token)")


class ProxmoxClusterUpdate(BaseModel):
    """Schema for updating a Proxmox Cluster"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    datacenter: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    api_url: Optional[str] = None
    api_username: Optional[str] = None
    api_token_id: Optional[str] = None
    api_token_secret: Optional[str] = None
    api_password: Optional[str] = None
    verify_ssl: Optional[bool] = None
    is_active: Optional[bool] = None


class ProxmoxClusterResponse(ProxmoxClusterBase):
    """Schema for Proxmox Cluster response"""
    id: str
    total_cpu_cores: Optional[int] = None
    total_memory_mb: Optional[int] = None
    total_storage_gb: Optional[int] = None
    last_sync: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProxmoxClusterListResponse(BaseModel):
    """Schema for paginated cluster list"""
    items: list[ProxmoxClusterResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ClusterTestRequest(BaseModel):
    """Schema for testing cluster connection"""
    api_url: str
    api_username: str
    api_token_id: Optional[str] = None
    api_token_secret: Optional[str] = None
    api_password: Optional[str] = None
    verify_ssl: bool = True


class ClusterTestResponse(BaseModel):
    """Schema for cluster test response"""
    success: bool
    message: str
    version: Optional[str] = None
    nodes: Optional[list[str]] = None
