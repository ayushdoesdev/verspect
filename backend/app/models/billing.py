"""Billing / subscription models — provider-agnostic SaaS plans."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    # active | trialing | past_due | canceled | incomplete | unpaid

    billing_interval: Mapped[str] = mapped_column(String(16), default="month", nullable=False)
    # month | year

    billing_provider: Mapped[str] = mapped_column(
        String(32), default="stripe", nullable=False, index=True
    )
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    provider_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Legacy Stripe columns — dual-written when billing_provider == stripe
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seat_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scheduled plan changes (downgrades / cancel→evaluation) — never destroy data early
    pending_plan: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    pending_interval: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    pending_change_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # upgrade | downgrade | cancel
    pending_change_effective_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="subscription")
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice",
        back_populates="subscription",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class FeatureUsageEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks premium feature usage for metering and future plan limits."""

    __tablename__ = "feature_usage_events"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # e.g. ai_migration_assistant

    repository_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dependency_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    simulation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("upgrade_simulations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    month_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    # YYYY-MM for monthly aggregation
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(12, 6), nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "invoices"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    billing_provider: Mapped[str] = mapped_column(
        String(32), default="stripe", nullable=False, index=True
    )
    provider_invoice_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    provider_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    # Legacy Stripe column — dual-written when billing_provider == stripe
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="usd", nullable=False)
    hosted_invoice_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invoice_pdf: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="invoices")
