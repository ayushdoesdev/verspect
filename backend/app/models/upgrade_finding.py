"""Persisted deterministic upgrade-impact / breaking-change findings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency
    from app.models.repository import Repository
    from app.models.upgrade_simulation import UpgradeSimulation


class UpgradeFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One API-level change compared against repository usage evidence."""

    __tablename__ = "upgrade_findings"

    simulation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("upgrade_simulations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
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
    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_version: Mapped[str] = mapped_column(String(64), nullable=False)
    target_version: Mapped[str] = mapped_column(String(64), nullable=False)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    affected_api: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_files: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    analysis_source: Mapped[str] = mapped_column(String(32), nullable=False, default="deterministic")
    official_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_breaking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    simulation: Mapped[Optional["UpgradeSimulation"]] = relationship("UpgradeSimulation")
    dependency: Mapped["Dependency"] = relationship("Dependency")
    repository: Mapped["Repository"] = relationship("Repository")
