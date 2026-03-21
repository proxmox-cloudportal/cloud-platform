"""
Resource quota model for managing organization resource limits.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Float, ForeignKey, DateTime, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.organization import Organization


class ResourceQuota(BaseModel):
    """
    Resource quotas and usage tracking per organization.

    Tracks limits and current usage for various resource types:
    - cpu_cores: Total CPU cores
    - memory_gb: Total memory in GB
    - storage_gb: Total storage in GB
    - vm_count: Number of VMs
    - cluster_count: Number of clusters
    """

    __tablename__ = "resource_quotas"

    # Foreign Key
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Resource type: cpu_cores, memory_gb, storage_gb, vm_count, cluster_count
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )

    # Quota limits
    limit_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0
    )

    # Current usage (calculated/cached)
    used_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0
    )

    # Metadata
    last_calculated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'resource_type', name='uq_org_resource'),
        Index('idx_quotas_org_resource', 'organization_id', 'resource_type'),
        CheckConstraint('limit_value >= 0', name='check_positive_limit'),
        CheckConstraint('used_value >= 0', name='check_positive_usage'),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="quotas",
        lazy="selectin"
    )

    @property
    def remaining(self) -> float:
        """Calculate remaining quota."""
        return max(0, self.limit_value - self.used_value)

    @property
    def usage_percentage(self) -> float:
        """Calculate usage as percentage."""
        if self.limit_value == 0:
            return 0.0
        return (self.used_value / self.limit_value) * 100

    def has_available_quota(self, requested_amount: float) -> bool:
        """Check if requested amount is within quota."""
        return self.used_value + requested_amount <= self.limit_value

    def __repr__(self) -> str:
        return f"<ResourceQuota(org_id={self.organization_id}, type={self.resource_type}, used={self.used_value}/{self.limit_value})>"
