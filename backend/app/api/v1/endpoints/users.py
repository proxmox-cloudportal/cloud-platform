"""
User management endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, UserListResponse
from app.core.deps import get_current_user, get_current_superadmin
from app.core.security import get_password_hash
from app.core.config import settings

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user's profile.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user profile
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Update current user's profile.

    Args:
        user_update: Fields to update
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user profile
    """
    # Update fields
    if user_update.email is not None:
        # Check if email is already taken
        result = await db.execute(
            select(User).where(
                User.email == user_update.email,
                User.id != current_user.id,
                User.deleted_at.is_(None)
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        current_user.email = user_update.email
        current_user.email_verified = False  # Require re-verification

    if user_update.first_name is not None:
        current_user.first_name = user_update.first_name

    if user_update.last_name is not None:
        current_user.last_name = user_update.last_name

    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by email or username"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List all users (superadmin only).

    Args:
        page: Page number
        per_page: Items per page
        search: Search query
        is_active: Filter by active status
        current_user: Current superadmin user
        db: Database session

    Returns:
        Paginated list of users
    """
    # Build query
    query = select(User).where(User.deleted_at.is_(None))

    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_filter)) |
            (User.username.ilike(search_filter))
        )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination
    query = query.offset((page - 1) * per_page).limit(per_page)

    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "data": users,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get user by ID (superadmin only).

    Args:
        user_id: User ID
        current_user: Current superadmin user
        db: Database session

    Returns:
        User details

    Raises:
        HTTPException: If user not found
    """
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete user (superadmin only).

    Args:
        user_id: User ID to delete
        current_user: Current superadmin user
        db: Database session

    Returns:
        No content

    Raises:
        HTTPException: If user not found or trying to delete self
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Soft delete
    from datetime import datetime
    user.deleted_at = datetime.utcnow()
    user.is_active = False

    await db.commit()

    return None
