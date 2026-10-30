"""User model — GitHub / Google / email authenticated accounts."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.organization import OrganizationMember
    from app.models.repository import Repository
    from app.models.scan import Scan


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    # Identity — github_id nullable for email/Google users
    github_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True, index=True)
    github_login: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(32), default="github", nullable=False)
    # github | google | email

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    github_access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_token_scopes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Active organization context
    active_organization_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL", use_alter=True, name="fk_users_active_org"),
        nullable=True,
        index=True,
    )

    # Notification preferences
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    slack_notifications: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notify_on_critical_cve: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_major_release: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_license_violation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    license_policy_override: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    repositories: Mapped[List["Repository"]] = relationship(
        "Repository",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="Repository.owner_id",
    )
    scans: Mapped[List["Scan"]] = relationship(
        "Scan",
        back_populates="triggered_by_user",
        lazy="selectin",
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="user",
        lazy="selectin",
    )
    memberships: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="user",
        foreign_keys="OrganizationMember.user_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.github_login}>"
