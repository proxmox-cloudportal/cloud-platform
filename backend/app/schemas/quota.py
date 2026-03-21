"""
Pydantic schemas for resource quotas.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class QuotaUpdateRequest(BaseModel):
    """Request to update quota limit."""
    limit_value: float = Field(..., ge=0, description="New quota limit (must be non-negative)")


class QuotaResponse(BaseModel):
    """Response for single quota."""
    id: str
    organization_id: str
    resource_type: str
    limit_value: float
    used_value: float
    last_calculated_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    # Computed fields
    @property
    def remaining(self) -> float:
        """Calculate remaining quota."""
        return max(0, self.limit_value - self.used_value)

    @property
    def usage_percentage(self) -> float:
        """Calculate usage as percentage."""
        if self.limit_value == 0:
            return 0.0
        return (self.used_value / self.limit_value) * 100


class QuotaResourceUsage(BaseModel):
    """Usage details for a single resource type."""
    resource_type: str
    resource_name: str
    used: float
    limit: float
    remaining: float
    usage_percentage: float
    last_calculated: Optional[datetime] = None


class QuotaUsageResponse(BaseModel):
    """Response with all quota usage details."""
    organization_id: str
    resources: List[QuotaResourceUsage]


class QuotaCheckResponse(BaseModel):
    """Response for quota availability check."""
    is_available: bool
    exceeded_resources: List[str]
    current_usage: dict
    limits: dict
    remaining: dict
