"""CVE model — OSV vulnerability records linked to dependencies."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import AlertSeverity
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency


class CVE(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cves"
    __table_args__ = (
        UniqueConstraint("dependency_id", "osv_id", name="uq_cves_dep_osv"),
    )

    dependency_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    osv_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    cve_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    aliases: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(32),
        default=AlertSeverity.MEDIUM.value,
        nullable=False,
        index=True,
    )
    cvss_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cvss_vector: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    affected_versions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    fixed_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    introduced_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_fixable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    references: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    raw_osv: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ecosystem: Mapped[str] = mapped_column(String(64), default="PyPI", nullable=False)

    dependency: Mapped["Dependency"] = relationship("Dependency", back_populates="cves")

    def __repr__(self) -> str:
        return f"<CVE {self.osv_id} severity={self.severity}>"
