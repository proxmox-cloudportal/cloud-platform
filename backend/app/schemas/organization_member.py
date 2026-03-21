"""
Pydantic schemas for organization membership.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MemberInviteRequest(BaseModel):
    """Request to invite user to organization."""
    user_id: str = Field(..., description="User ID to invite")
    role: str = Field(..., pattern="^(admin|member|viewer)$", description="Role to assign")


class MemberRoleUpdate(BaseModel):
    """Request to update member role."""
    role: str = Field(..., pattern="^(admin|member|viewer)$", description="New role")


class OrganizationMemberResponse(BaseModel):
    """Response for organization member."""
    id: str
    user_id: str
    organization_id: str
    role: str
    joined_at: datetime
    invited_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserInfo(BaseModel):
    """Basic user information."""
    id: str
    email: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    model_config = {"from_attributes": True}


class OrganizationInfo(BaseModel):
    """Basic organization information."""
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class OrganizationMemberDetailResponse(BaseModel):
    """Detailed response for organization member with user info."""
    id: str
    user_id: str
    organization_id: str
    role: str
    joined_at: datetime
    invited_by: Optional[str] = None
    user: UserInfo
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationMembershipResponse(BaseModel):
    """Response for user's organization membership."""
    organization: OrganizationInfo
    role: str
    joined_at: Optional[datetime] = None
