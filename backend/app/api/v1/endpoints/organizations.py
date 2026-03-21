"""
Organization management endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.core.deps import (
    get_current_user,
    get_organization_context,
    get_current_org_admin,
    OrgContext,
    RequirePermission
)
from app.core.rbac import Permission
from app.schemas.organization_member import (
    MemberInviteRequest,
    MemberRoleUpdate,
    OrganizationMemberDetailResponse,
    OrganizationMembershipResponse,
    UserInfo
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/me", response_model=List[OrganizationMembershipResponse])
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """
    List all organizations the current user belongs to.

    Returns list of organizations with user's role in each.
    """
    if current_user.is_superadmin:
        # Superadmins see all organizations
        result = await db.execute(
            select(Organization).where(Organization.deleted_at.is_(None))
        )
        orgs = result.scalars().all()

        return [
            {
                "organization": org,
                "role": "superadmin",
                "joined_at": None
            }
            for org in orgs
        ]

    # Get user's memberships
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.deleted_at.is_(None)
        )
    )
    memberships = result.scalars().all()

    return [
        {
            "organization": membership.organization,
            "role": membership.role,
            "joined_at": membership.joined_at
        }
        for membership in memberships
    ]


@router.get("/members", response_model=List[OrganizationMemberDetailResponse])
async def list_organization_members(
    org_context: OrgContext = Depends(RequirePermission(Permission.ORG_MEMBER_READ)),
    db: AsyncSession = Depends(get_db)
) -> List[OrganizationMember]:
    """
    List all members of an organization.

    Requires: ORG_MEMBER_READ permission
    """
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_context.org_id,
            OrganizationMember.deleted_at.is_(None)
        )
    )
    members = result.scalars().all()

    return members


@router.post("/members", response_model=OrganizationMemberDetailResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    invite_data: MemberInviteRequest,
    org_context: OrgContext = Depends(RequirePermission(Permission.ORG_MEMBER_INVITE)),
    db: AsyncSession = Depends(get_db)
) -> OrganizationMember:
    """
    Invite user to organization.

    Requires: ORG_MEMBER_INVITE permission (org admin or superadmin)
    """
    # Validate user exists
    result = await db.execute(
        select(User).where(
            User.id == invite_data.user_id,
            User.deleted_at.is_(None)
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if already member
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == invite_data.user_id,
            OrganizationMember.organization_id == org_context.org_id,
            OrganizationMember.deleted_at.is_(None)
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization"
        )

    # Create membership
    membership = OrganizationMember(
        user_id=invite_data.user_id,
        organization_id=org_context.org_id,
        role=invite_data.role,
        invited_by=org_context.user.id
    )

    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return membership


@router.patch("/members/{user_id}", response_model=OrganizationMemberDetailResponse)
async def update_member_role(
    user_id: str,
    role_update: MemberRoleUpdate,
    org_context: OrgContext = Depends(RequirePermission(Permission.ORG_MEMBER_UPDATE_ROLE)),
    db: AsyncSession = Depends(get_db)
) -> OrganizationMember:
    """
    Update member role in organization.

    Requires: ORG_MEMBER_UPDATE_ROLE permission (org admin or superadmin)
    """
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_context.org_id,
            OrganizationMember.deleted_at.is_(None)
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found"
        )

    # Prevent demoting yourself if you're the only admin
    if user_id == org_context.user.id and role_update.role != "admin":
        # Count other admins
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_context.org_id,
                OrganizationMember.role == "admin",
                OrganizationMember.deleted_at.is_(None)
            )
        )
        admin_count = len(result.scalars().all())

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own role when you are the only admin"
            )

    membership.role = role_update.role
    await db.commit()
    await db.refresh(membership)

    return membership


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.ORG_MEMBER_REMOVE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove member from organization.

    Requires: ORG_MEMBER_REMOVE permission (org admin or superadmin)
    """
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_context.org_id,
            OrganizationMember.deleted_at.is_(None)
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found"
        )

    # Prevent removing yourself if you're the only admin
    if user_id == org_context.user.id:
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_context.org_id,
                OrganizationMember.role == "admin",
                OrganizationMember.deleted_at.is_(None)
            )
        )
        admin_count = len(result.scalars().all())

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove yourself when you are the only admin"
            )

    # Soft delete
    from datetime import datetime
    membership.deleted_at = datetime.utcnow()
    await db.commit()
