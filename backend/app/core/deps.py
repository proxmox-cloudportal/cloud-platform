"""
FastAPI dependencies for authentication and database access.
"""
from typing import Optional

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.core.security import decode_token
from app.core.rbac import Role, Permission, has_permission

# HTTP Bearer token authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        Current user object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    # Decode token
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user ID from token
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user.

    Args:
        current_user: Current user from token

    Returns:
        Active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_superadmin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current superadmin user.

    Args:
        current_user: Current user from token

    Returns:
        Superadmin user

    Raises:
        HTTPException: If user is not a superadmin
    """
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    Useful for endpoints that work differently for authenticated users.

    Args:
        credentials: Optional bearer token
        db: Database session

    Returns:
        User if authenticated, None otherwise
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = decode_token(token)
        if payload is None:
            return None

        user_id = payload.get("sub")
        if user_id is None:
            return None

        # Would need to make this async properly
        # For now, return None if optional auth
        return None
    except Exception:
        return None


# ============================================================================
# Organization Context and RBAC Dependencies
# ============================================================================

class OrgContext:
    """
    Organization context for requests.

    Encapsulates organization, user, role, and permission checking.
    """

    def __init__(
        self,
        org_id: str,
        user: User,
        role: Role,
        membership: Optional[OrganizationMember] = None
    ):
        self.org_id = org_id
        self.user = user
        self.role = role
        self.membership = membership

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has permission in this organization."""
        if self.user.is_superadmin:
            return True
        return has_permission(self.role, permission)

    def is_admin(self) -> bool:
        """Check if user is org admin or superadmin."""
        return self.role in [Role.SUPERADMIN, Role.ORG_ADMIN]

    def is_member_or_higher(self) -> bool:
        """Check if user is at least a member (not just viewer)."""
        return self.role in [Role.SUPERADMIN, Role.ORG_ADMIN, Role.ORG_MEMBER]

    def __repr__(self) -> str:
        return f"<OrgContext(org_id={self.org_id}, user={self.user.email}, role={self.role.value})>"


async def get_organization_context(
    org_id: str = Header(..., alias="X-Organization-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> OrgContext:
    """
    Get organization context from header.

    Validates user membership and returns context with role.

    Args:
        org_id: Organization ID from X-Organization-ID header
        current_user: Current authenticated user
        db: Database session

    Returns:
        OrgContext with organization, user, and role information

    Raises:
        HTTPException: If organization not found or user not a member
    """
    # Superadmins have access to all organizations
    if current_user.is_superadmin:
        result = await db.execute(
            select(Organization).where(
                Organization.id == org_id,
                Organization.deleted_at.is_(None)
            )
        )
        org = result.scalar_one_or_none()

        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

        # Create virtual context for superadmin
        return OrgContext(
            org_id=org_id,
            user=current_user,
            role=Role.SUPERADMIN,
            membership=None
        )

    # Check user membership
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.organization_id == org_id,
            OrganizationMember.deleted_at.is_(None)
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization"
        )

    # Check organization is active
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.deleted_at.is_(None)
        )
    )
    org = result.scalar_one_or_none()

    if not org or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is not active"
        )

    return OrgContext(
        org_id=org_id,
        user=current_user,
        role=Role(membership.role),
        membership=membership
    )


async def get_current_org_admin(
    org_context: OrgContext = Depends(get_organization_context)
) -> OrgContext:
    """
    Require org admin or superadmin role.

    Args:
        org_context: Organization context

    Returns:
        OrgContext if user is admin

    Raises:
        HTTPException: If user is not an admin
    """
    if org_context.role not in [Role.SUPERADMIN, Role.ORG_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin privileges required"
        )
    return org_context


def RequirePermission(permission: Permission):
    """
    Factory function to create permission dependency.

    Usage:
        @router.post("/vms")
        async def create_vm(
            org_context: OrgContext = Depends(RequirePermission(Permission.VM_CREATE))
        ):
            ...

    Args:
        permission: Required permission

    Returns:
        Dependency function that checks permission
    """
    async def _require_permission(
        org_context: OrgContext = Depends(get_organization_context)
    ) -> OrgContext:
        if not org_context.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}"
            )
        return org_context

    return _require_permission
