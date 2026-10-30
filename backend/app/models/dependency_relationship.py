"""Dependency relationship edges (direct → transitive / depends_on)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency


class DependencyRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Directed edge: parent_dependency depends on child_dependency."""

    __tablename__ = "dependency_relationships"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "parent_dependency_id",
            "child_dependency_id",
            "edge_type",
            name="uq_dep_rel_repo_parent_child_rel",
        ),
    )

    repository_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_dependency_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_dependency_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_type: Mapped[str] = mapped_column(
        String(64),
        default="depends_on",
        nullable=False,
    )
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    parent: Mapped["Dependency"] = orm_relationship(
        "Dependency",
        foreign_keys=[parent_dependency_id],
    )
    child: Mapped["Dependency"] = orm_relationship(
        "Dependency",
        foreign_keys=[child_dependency_id],
    )
