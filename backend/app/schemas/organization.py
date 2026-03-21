"""
Pydantic schemas for Organization API requests and responses.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# Base schema
class OrganizationBase(BaseModel):
    """Base organization schema."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: Optional[str] = None


# Request schemas
class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "description": "Main organization for Acme Corp"
            }
        }
    )


class OrganizationUpdate(BaseModel):
    """Schema for updating organization."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corporation Updated",
                "description": "Updated description"
            }
        }
    )


# Response schemas
class OrganizationResponse(OrganizationBase):
    """Schema for organization response."""

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationListResponse(BaseModel):
    """Schema for paginated organization list response."""

    data: list[OrganizationResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
