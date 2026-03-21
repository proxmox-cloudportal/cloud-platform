"""
Organization membership model for multi-tenancy support.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Organization


class OrganizationMember(BaseModel):
    """
    Organization membership with role-based access control.

    Establishes many-to-many relationship between users and organizations,
    with role information for RBAC.
    """

    __tablename__ = "organization_members"

    # Foreign Keys
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Role: admin, member, viewer
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="member"
    )

    # Membership metadata
    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    invited_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'organization_id', name='uq_user_org'),
        Index('idx_org_members_org_role', 'organization_id', 'role'),
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin"
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="members",
        lazy="selectin"
    )

    inviter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[invited_by],
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<OrganizationMember(user_id={self.user_id}, org_id={self.organization_id}, role={self.role})>"
