"""Pydantic schemas for VPC Network API."""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
import ipaddress


class NetworkCreate(BaseModel):
    """Schema for creating a new VPC network."""

    name: str = Field(..., min_length=1, max_length=255, description="Network name")
    description: Optional[str] = Field(None, description="Network description")
    cidr: str = Field(..., description="CIDR notation (e.g., 10.100.0.0/24)")
    gateway: Optional[str] = Field(None, description="Gateway IP address")
    dns_servers: Optional[List[str]] = Field(default_factory=list, description="DNS servers")
    is_shared: bool = Field(default=False, description="Share network within organization")
    bridge: str = Field(default="vmbr0", description="Proxmox bridge name")

    @field_validator('cidr')
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        """Validate CIDR notation."""
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid CIDR notation: {e}")
        return v

    @field_validator('gateway')
    @classmethod
    def validate_gateway(cls, v: Optional[str]) -> Optional[str]:
        """Validate gateway IP address."""
        if v is None:
            return v
        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"Invalid gateway IP address: {e}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Production Network",
                "description": "Primary production network for web services",
                "cidr": "10.100.0.0/24",
                "gateway": "10.100.0.1",
                "dns_servers": ["8.8.8.8", "8.8.4.4"],
                "is_shared": False,
                "bridge": "vmbr0"
            }
        }
    )


class NetworkUpdate(BaseModel):
    """Schema for updating a VPC network."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    gateway: Optional[str] = None
    dns_servers: Optional[List[str]] = None
    is_shared: Optional[bool] = None

    @field_validator('gateway')
    @classmethod
    def validate_gateway(cls, v: Optional[str]) -> Optional[str]:
        """Validate gateway IP address."""
        if v is None:
            return v
        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"Invalid gateway IP address: {e}")
        return v


class NetworkResponse(BaseModel):
    """Schema for network response."""

    id: str
    organization_id: str
    created_by: str
    name: str
    description: Optional[str]
    vlan_id: int
    bridge: str
    cidr: str
    gateway: Optional[str]
    dns_servers: Optional[List[str]]
    is_shared: bool
    is_default: bool
    tags: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NetworkListResponse(BaseModel):
    """Schema for paginated network list response."""

    data: List[NetworkResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class IPPoolCreate(BaseModel):
    """Schema for creating IP pool."""

    pool_name: str = Field(..., min_length=1, max_length=255)
    start_ip: str = Field(..., description="Start IP address")
    end_ip: str = Field(..., description="End IP address")
    description: Optional[str] = None

    @field_validator('start_ip', 'end_ip')
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """Validate IP address."""
        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"Invalid IP address: {e}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pool_name": "VM Pool",
                "start_ip": "10.100.0.10",
                "end_ip": "10.100.0.250",
                "description": "IP pool for virtual machines"
            }
        }
    )


class IPPoolResponse(BaseModel):
    """Schema for IP pool response."""

    id: str
    network_id: str
    pool_name: str
    start_ip: str
    end_ip: str
    description: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IPAllocationRequest(BaseModel):
    """Schema for IP allocation request."""

    ip_pool_id: Optional[str] = Field(None, description="IP pool ID to allocate from")
    preferred_ip: Optional[str] = Field(None, description="Preferred IP address")

    @field_validator('preferred_ip')
    @classmethod
    def validate_preferred_ip(cls, v: Optional[str]) -> Optional[str]:
        """Validate preferred IP address."""
        if v is None:
            return v
        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"Invalid IP address: {e}")
        return v


class IPAllocationResponse(BaseModel):
    """Schema for IP allocation response."""

    id: str
    network_id: str
    ip_pool_id: Optional[str]
    ip_address: str
    vm_id: Optional[str]
    interface_name: Optional[str]
    status: str
    hostname: Optional[str]
    mac_address: Optional[str]
    notes: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VMNetworkAttachRequest(BaseModel):
    """Schema for attaching network to VM."""

    network_id: str = Field(..., description="Network ID to attach")
    interface_order: int = Field(..., ge=0, le=3, description="Interface order (0-3 for net0-net3)")
    model: str = Field(default="virtio", description="NIC model (virtio, e1000, rtl8139)")
    allocate_ip: bool = Field(default=True, description="Auto-allocate IP address")
    ip_pool_id: Optional[str] = Field(None, description="Specific IP pool to allocate from")

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate NIC model."""
        allowed = ['virtio', 'e1000', 'rtl8139']
        if v.lower() not in allowed:
            raise ValueError(f"model must be one of: {', '.join(allowed)}")
        return v.lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "network_id": "net-123",
                "interface_order": 0,
                "model": "virtio",
                "allocate_ip": True
            }
        }
    )


class VMNetworkInterfaceResponse(BaseModel):
    """Schema for VM network interface response."""

    id: str
    vm_id: str
    network_id: str
    interface_name: str
    mac_address: Optional[str]
    model: str
    ip_allocation_id: Optional[str]
    is_primary: bool
    interface_order: int
    proxmox_config: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
