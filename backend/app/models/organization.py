"""
Organization model for multi-tenancy.
"""
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.organization_member import OrganizationMember
    from app.models.resource_quota import ResourceQuota
    from app.models.virtual_machine import VirtualMachine


class Organization(BaseModel):
    """Organization model for multi-tenant support."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # JSON settings for organization-specific configuration
    settings: Mapped[Optional[dict]] = mapped_column(JSON, default={}, nullable=True)

    # Relationships
    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    quotas: Mapped[List["ResourceQuota"]] = relationship(
        "ResourceQuota",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    virtual_machines: Mapped[List["VirtualMachine"]] = relationship(
        "VirtualMachine",
        back_populates="organization",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, slug={self.slug})>"
