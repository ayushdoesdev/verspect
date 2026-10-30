"""UpgradeSimulation — AI Upgrade Impact Simulator results."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import SimulationStatus
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency
    from app.models.repository import Repository
    from app.models.user import User


class UpgradeSimulation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "upgrade_simulations"

    dependency_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_version: Mapped[str] = mapped_column(String(64), nullable=False)
    to_version: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(
        String(64),
        default=SimulationStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Cache key for identical simulations
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Report fields
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    safe_to_upgrade: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    readiness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    migration_time_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    migration_time_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    breaking_apis: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    deprecated_apis: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    affected_files: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    affected_symbols: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    affected_functions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    affected_classes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    security_improvements: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    performance_improvements: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    manual_work_required: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    automatic_fixes_possible: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    migration_plan: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    suggested_changes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    readiness_factors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    # Collected source material (for audit / re-analysis)
    collected_sources: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    usage_snapshot: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    raw_ai_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Worker lifecycle / observability (mirrors Scan)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    worker_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage_timings: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    dependency: Mapped["Dependency"] = relationship("Dependency", back_populates="upgrade_simulations")
    repository: Mapped["Repository"] = relationship("Repository")
    triggered_by_user: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<UpgradeSimulation {self.package_name} "
            f"{self.from_version}->{self.to_version} status={self.status}>"
        )
