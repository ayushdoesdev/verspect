"""Repository model — GitHub repositories under watch."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import RepositorySyncStatus
from app.core.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.dependency import Dependency
    from app.models.organization import Organization
    from app.models.scan import Scan
    from app.models.user import User


class Repository(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("owner_id", "github_repo_id", name="uq_repositories_owner_github"),
    )

    owner_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    github_repo_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_login: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_url: Mapped[str] = mapped_column(Text, nullable=False)
    clone_url: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), default="main", nullable=False)
    # GitHub-reported primary language (hint only)
    language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Classifier results (authoritative for pipeline routing / UI)
    detected_language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detected_language_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, index=True
    )
    detected_framework: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    package_manager: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    support_status: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, index=True
    )
    # Full ClassificationResult.to_dict() snapshot from last scan
    classification: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_fork: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stars_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    forks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Watch / sync state
    is_watching: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    webhook_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sync_status: Mapped[str] = mapped_column(
        String(32),
        default=RepositorySyncStatus.NEVER_SYNCED.value,
        nullable=False,
        index=True,
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_scan_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Aggregate health metrics (denormalized for dashboard speed)
    dependency_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outdated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vulnerable_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_alert_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    health_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    license_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    topics: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="repositories")
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        back_populates="repositories",
    )
    # noload: list/detail APIs serialize counters only. selectin here pulled
    # every dependency/scan/alert for the page and blocked the API after npm scans.
    dependencies: Mapped[List["Dependency"]] = relationship(
        "Dependency",
        back_populates="repository",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    scans: Mapped[List["Scan"]] = relationship(
        "Scan",
        back_populates="repository",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="repository",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Repository {self.full_name}>"
