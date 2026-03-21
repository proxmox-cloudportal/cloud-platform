"""
Snapshot schemas for VM snapshot management.
"""
from typing import Optional
from pydantic import BaseModel, Field


class SnapshotCreate(BaseModel):
    """Schema for creating a snapshot."""

    name: str = Field(..., min_length=1, max_length=100, description="Snapshot name")
    description: Optional[str] = Field(None, max_length=500, description="Snapshot description")
    include_memory: bool = Field(default=False, description="Include VM memory state (for running VMs)")


class SnapshotResponse(BaseModel):
    """Schema for snapshot information."""

    name: str = Field(..., description="Snapshot name")
    description: Optional[str] = Field(None, description="Snapshot description")
    snaptime: Optional[int] = Field(None, description="Snapshot creation timestamp")
    vmstate: Optional[int] = Field(None, description="Whether VM memory is included")
    parent: Optional[str] = Field(None, description="Parent snapshot name")

    class Config:
        from_attributes = True


class SnapshotListResponse(BaseModel):
    """Schema for list of snapshots."""

    data: list[SnapshotResponse]
    total: int
