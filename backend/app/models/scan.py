"""Scan model — audit trail for repository scan jobs."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import ScanStatus, ScanType
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.user import User


class Scan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scans"

    repository_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scan_type: Mapped[str] = mapped_column(
        String(32),
        default=ScanType.MANUAL.value,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(64),
        default=ScanStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    previous_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Worker lifecycle / observability
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    worker_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # [{stage, started_at, completed_at, duration_seconds}]
    stage_timings: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    # Counts produced by this scan
    dependencies_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usages_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vulnerabilities_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alerts_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_parsed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outdated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    license_issues: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    manifest_files: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="scans")
    triggered_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="scans",
    )

    def __repr__(self) -> str:
        return f"<Scan {self.id} status={self.status} type={self.scan_type}>"
