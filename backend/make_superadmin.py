"""
Quick script to make a user a superadmin.

Usage:
    python make_superadmin.py user@example.com
"""
import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.user import User


async def make_superadmin(email: str):
    """Make a user a superadmin."""

    # Create async engine
    engine = create_async_engine(str(settings.DATABASE_URL), echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Find user
        result = await session.execute(
            select(User).where(
                User.email == email,
                User.deleted_at.is_(None)
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"❌ User not found: {email}")
            return

        if user.is_superadmin:
            print(f"ℹ️  User {user.email} is already a superadmin")
            return

        # Update to superadmin
        user.is_superadmin = True
        await session.commit()

        print(f"✅ User {user.email} is now a superadmin!")
        print(f"   ID: {user.id}")
        print(f"   Username: {user.username}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_superadmin.py user@example.com")
        sys.exit(1)

    email = sys.argv[1]
    asyncio.run(make_superadmin(email))
