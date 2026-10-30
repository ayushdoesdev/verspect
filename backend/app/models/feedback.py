"""User feedback submissions for Private Beta."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class FeedbackSubmission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "feedback_submissions"

    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    repository: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    page_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    app_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    browser: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    priority: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="medium",
        server_default="medium",
        index=True,
    )
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="open",
        server_default="open",
        index=True,
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
