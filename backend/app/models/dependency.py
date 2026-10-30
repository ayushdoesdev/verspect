"""Dependency and DependencyVersion models."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
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
from app.core.enums import DependencyStatus
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.alternative import AlternativeLibrary
    from app.models.cve import CVE
    from app.models.library_usage import LibraryUsage
    from app.models.migration import MigrationReport
    from app.models.release import Release
    from app.models.repository import Repository
    from app.models.upgrade_simulation import UpgradeSimulation


class Dependency(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dependencies"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "package_name",
            "ecosystem",
            name="uq_dependencies_repo_package_eco",
        ),
    )

    repository_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ecosystem: Mapped[str] = mapped_column(String(64), default="PyPI", nullable=False)
    manifest_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_direct: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_dev: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Version info (denormalized latest known)
    current_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    latest_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    version_constraint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_outdated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    major_behind: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minor_behind: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    patch_behind: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # License
    license_spdx: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    license_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license_policy_action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Health & status
    status: Mapped[str] = mapped_column(
        String(32),
        default=DependencyStatus.UNKNOWN.value,
        nullable=False,
        index=True,
    )
    health_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    has_vulnerabilities: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vulnerability_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_vuln_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # PyPI / package metadata
    pypi_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    home_page: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    requires_python: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    download_count_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    github_stars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    github_repo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_release_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_commit_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    open_issues: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    release_frequency_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # AI summaries (cached)
    ai_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_should_update: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_security_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="dependencies")
    versions: Mapped[List["DependencyVersion"]] = relationship(
        "DependencyVersion",
        back_populates="dependency",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DependencyVersion.released_at.desc()",
    )
    usages: Mapped[List["LibraryUsage"]] = relationship(
        "LibraryUsage",
        back_populates="dependency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    cves: Mapped[List["CVE"]] = relationship(
        "CVE",
        back_populates="dependency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    releases: Mapped[List["Release"]] = relationship(
        "Release",
        back_populates="dependency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    migration_reports: Mapped[List["MigrationReport"]] = relationship(
        "MigrationReport",
        back_populates="dependency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    alternatives: Mapped[List["AlternativeLibrary"]] = relationship(
        "AlternativeLibrary",
        back_populates="dependency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="dependency",
        lazy="selectin",
    )
    upgrade_simulations: Mapped[List["UpgradeSimulation"]] = relationship(
        "UpgradeSimulation",
        back_populates="dependency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Dependency {self.package_name}@{self.current_version}>"


class DependencyVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dependency_versions"
    __table_args__ = (
        UniqueConstraint(
            "dependency_id",
            "version",
            name="uq_dependency_versions_dep_version",
        ),
    )

    dependency_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_yanked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    requires_python: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    yanked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    download_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    dependency: Mapped["Dependency"] = relationship("Dependency", back_populates="versions")

    def __repr__(self) -> str:
        return f"<DependencyVersion {self.version}>"
