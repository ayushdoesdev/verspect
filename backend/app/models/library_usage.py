"""LibraryUsage — AST-extracted API usage sites."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import UsageKind
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency
    from app.models.repository import Repository


class LibraryUsage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "library_usages"
    __table_args__ = (
        UniqueConstraint(
            "dependency_id",
            "file_path",
            "line",
            "column",
            "symbol",
            "usage_kind",
            name="uq_library_usages_location",
        ),
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
    module_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    symbol: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    fully_qualified_name: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    usage_kind: Mapped[str] = mapped_column(
        String(64),
        default=UsageKind.IMPORT.value,
        nullable=False,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    line: Mapped[int] = mapped_column(Integer, nullable=False)
    column: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_column: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    enclosing_function: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    enclosing_class: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    code_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alias: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    dependency: Mapped["Dependency"] = relationship("Dependency", back_populates="usages")
    repository: Mapped["Repository"] = relationship("Repository")

    def __repr__(self) -> str:
        return f"<LibraryUsage {self.fully_qualified_name} @ {self.file_path}:{self.line}>"
