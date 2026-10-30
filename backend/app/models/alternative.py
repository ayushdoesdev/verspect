"""AlternativeLibrary — recommended replacement packages."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import MigrationDifficulty
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency


class AlternativeLibrary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "alternative_libraries"
    __table_args__ = (
        UniqueConstraint(
            "dependency_id",
            "alternative_name",
            name="uq_alternative_libraries_dep_alt",
        ),
    )

    dependency_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alternative_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alternative_normalized: Mapped[str] = mapped_column(String(255), nullable=False)

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    pros: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    cons: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    popularity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    health_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    download_count_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    github_stars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    migration_effort: Mapped[str] = mapped_column(
        String(32),
        default=MigrationDifficulty.MEDIUM.value,
        nullable=False,
    )
    api_compatibility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    license_spdx: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    pypi_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    home_page: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="ai", nullable=False)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    dependency: Mapped["Dependency"] = relationship("Dependency", back_populates="alternatives")

    def __repr__(self) -> str:
        return f"<AlternativeLibrary {self.package_name} -> {self.alternative_name}>"
