"""MigrationReport — AI-generated migration guidance."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import MigrationDifficulty
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency
    from app.models.repository import Repository


class MigrationReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "migration_reports"

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

    from_version: Mapped[str] = mapped_column(String(64), nullable=False)
    to_version: Mapped[str] = mapped_column(String(64), nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(
        String(32),
        default=MigrationDifficulty.MEDIUM.value,
        nullable=False,
    )
    risk_score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    estimated_effort_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    breaking_changes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    api_mappings: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    affected_files: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    step_by_step: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    code_examples: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    testing_checklist: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    rollback_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    should_update: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    dependency: Mapped["Dependency"] = relationship("Dependency", back_populates="migration_reports")
    repository: Mapped["Repository"] = relationship("Repository")

    def __repr__(self) -> str:
        return f"<MigrationReport {self.package_name} {self.from_version}->{self.to_version}>"
