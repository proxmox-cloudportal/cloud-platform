"""
Quick script to add all existing users to the default organization.
Run this after migrations to ensure all users have organization access.

Usage:
    python add_users_to_default_org.py
"""
import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember


async def add_users_to_default_org():
    """Add all users to the default organization as admins."""

    # Create async engine
    engine = create_async_engine(str(settings.DATABASE_URL), echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get default organization
        result = await session.execute(
            select(Organization).where(
                Organization.slug == "default",
                Organization.deleted_at.is_(None)
            )
        )
        default_org = result.scalar_one_or_none()

        if not default_org:
            print("❌ Default organization not found!")
            print("   Run migrations first: alembic upgrade head")
            return

        print(f"✓ Found default organization: {default_org.name} (ID: {default_org.id})")

        # Get all active users
        result = await session.execute(
            select(User).where(User.deleted_at.is_(None))
        )
        users = result.scalars().all()

        print(f"✓ Found {len(users)} users")

        # Add each user to default org if not already a member
        added_count = 0
        skipped_count = 0

        for user in users:
            # Check if already a member
            result = await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.organization_id == default_org.id,
                    OrganizationMember.deleted_at.is_(None)
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  ⊘ Skipping {user.email} (already a member)")
                skipped_count += 1
                continue

            # Create membership
            membership = OrganizationMember(
                id=str(uuid.uuid4()),
                user_id=user.id,
                organization_id=default_org.id,
                role="admin",  # Make all users admins initially
                joined_at=datetime.utcnow()
            )
            session.add(membership)
            print(f"  ✓ Added {user.email} as admin")
            added_count += 1

        # Commit all changes
        await session.commit()

        print(f"\n✅ Done!")
        print(f"   Added: {added_count} users")
        print(f"   Skipped: {skipped_count} users")
        print(f"\n🎉 All users can now log in and access the platform!")


if __name__ == "__main__":
    asyncio.run(add_users_to_default_org())
