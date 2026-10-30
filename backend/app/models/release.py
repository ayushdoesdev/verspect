"""Release model — package release notes and AI analysis."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import MigrationDifficulty
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency


class Release(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint("dependency_id", "version", name="uq_releases_dep_version"),
    )

    dependency_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_major: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_minor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_patch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    release_notes_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    release_notes_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changelog_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    breaking_changes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    deprecated_apis: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    new_features: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    bug_fixes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    migration_difficulty: Mapped[Optional[str]] = mapped_column(
        String(32),
        default=MigrationDifficulty.LOW.value,
        nullable=True,
    )
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    affected_symbols: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    affected_files_in_repo: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    ai_analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    has_breaking_changes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    dependency: Mapped["Dependency"] = relationship("Dependency", back_populates="releases")

    def __repr__(self) -> str:
        return f"<Release {self.package_name}@{self.version}>"
