"""
Authentication endpoints for login, register, and token refresh.
"""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.schemas.user import (
    UserCreate,
    UserResponse,
    Token,
    LoginRequest,
    RefreshTokenRequest,
)
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Register a new user account.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException: If email or username already exists
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email, User.deleted_at.is_(None))
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username already exists
    result = await db.execute(
        select(User).where(User.username == user_data.username, User.deleted_at.is_(None))
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Get or create the default organization and add user as admin
    result = await db.execute(
        select(Organization).where(
            Organization.slug == "default",
            Organization.deleted_at.is_(None)
        )
    )
    default_org = result.scalar_one_or_none()

    if not default_org:
        default_org = Organization(
            id=str(uuid.uuid4()),
            name="Default",
            slug="default",
            description="Default organization",
            is_active=True,
        )
        db.add(default_org)
        await db.flush()

    membership = OrganizationMember(
        id=str(uuid.uuid4()),
        user_id=user.id,
        organization_id=default_org.id,
        role="admin",
        joined_at=datetime.utcnow(),
    )
    db.add(membership)
    await db.commit()

    return user


@router.post("/login", response_model=Token)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Authenticate user and return JWT tokens.

    Args:
        credentials: User login credentials
        db: Database session

    Returns:
        JWT access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == credentials.email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    # Verify credentials
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    # Create tokens
    access_token = create_access_token(subject=user.id, email=user.email)
    refresh_token = create_refresh_token(subject=user.id, email=user.email)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Refresh access token using refresh token.

    Args:
        token_data: Refresh token
        db: Database session

    Returns:
        New access token

    Raises:
        HTTPException: If refresh token is invalid
    """
    # Decode refresh token
    payload = decode_token(token_data.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    user_id = payload.get("sub")
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Create new access token
    access_token = create_access_token(subject=user.id, email=user.email)

    return {
        "access_token": access_token,
        "refresh_token": token_data.refresh_token,  # Return same refresh token
        "token_type": "Bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout current user.

    Note: In a stateless JWT implementation, logout is handled client-side
    by removing the tokens. For server-side logout, implement token blacklisting.

    Args:
        current_user: Current authenticated user

    Returns:
        No content
    """
    # In production, add token to blacklist (Redis)
    # For now, just return success
    return None


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current authenticated user's information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user details
    """
    return current_user
