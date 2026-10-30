"""Billing schemas."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    plan: str = Field(pattern="^(starter|pro|team)$")
    interval: str = Field(default="month", pattern="^(month|year)$")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutResponse(BaseModel):
    url: str
    session_id: str
    mode: str
    provider: Optional[str] = None


class PortalResponse(BaseModel):
    url: str
    mode: str
    provider: Optional[str] = None


class ChangePlanRequest(BaseModel):
    plan: str = Field(pattern="^(starter|pro|team|free)$")
    interval: str = Field(default="month", pattern="^(month|year)$")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class LifecycleActionResponse(BaseModel):
    action: str
    plan: str
    pending_plan: Optional[str] = None
    pending_change_type: Optional[str] = None
    pending_change_effective_at: Optional[datetime] = None
    cancel_at_period_end: bool = False
    current_period_end: Optional[datetime] = None
    message: str = ""
    checkout_url: Optional[str] = None
    mode: str = "local"
    provider: Optional[str] = None
    soft_limit_summary: Optional[dict[str, Any]] = None


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    billing_interval: str
    seat_count: int
    trial_ends_at: Optional[datetime] = None
    trial_active: bool = False
    evaluation_active: bool = False
    evaluation_expired: bool = False
    read_only: bool = False
    can_write: bool = True
    can_import_repositories: bool = True
    can_trigger_scans: bool = True
    can_sync_repositories: bool = True
    can_run_background_jobs: bool = True
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    pending_plan: Optional[str] = None
    pending_interval: Optional[str] = None
    pending_change_type: Optional[str] = None
    pending_change_effective_at: Optional[datetime] = None
    pending_change_message: Optional[str] = None
    can_upgrade: bool = True
    can_downgrade: bool = False
    can_cancel: bool = False
    can_reactivate: bool = False
    billing_provider: Optional[str] = None
    next_invoice_at: Optional[datetime] = None
    upgrade_simulator: bool = True
    ai_enabled: bool = False
    ai_migration_assistant: bool = False
    can_generate_ai_migration: bool = False
    can_view_ai_migration_reports: bool = True
    ai_migration_requests_this_month: int = 0
    ai_migration_tokens_this_month: int = 0
    ai_migration_cost_this_month: float = 0
    limits: dict[str, Any] = Field(default_factory=dict)
    price_monthly: Optional[float] = None
    price_label: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: UUID
    number: Optional[str] = None
    status: str
    amount_due: float
    amount_paid: float
    currency: str
    hosted_invoice_url: Optional[str] = None
    invoice_pdf: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class UsageResponse(BaseModel):
    plan: str
    repositories_used: int
    repositories_limit: Optional[int]
    members_used: int
    members_limit: Optional[int]
    monthly_scan_limit: Optional[int] = None
    monthly_scans_used: int = 0
    evaluation_active: bool = False
    evaluation_expired: bool = False
    read_only: bool = False
    can_write: bool = True
    upgrade_simulator: bool = True
    ai_enabled: bool
    ai_migration_assistant: bool = False
    can_generate_ai_migration: bool = False
    ai_migration_requests_this_month: int = 0
    ai_migration_tokens_this_month: int = 0
    ai_migration_cost_this_month: float = 0
    ai_migration_avg_ms: int = 0
    teams_enabled: bool
    api_access: bool
    scheduled_scans: bool
    webhooks: bool = False
    rbac: bool = False
    audit_logs: bool = False


class PricingCatalogResponse(BaseModel):
    plans: List[dict[str, Any]]
    feature_comparison: List[dict[str, Any]] = Field(default_factory=list)
    billing_provider: Optional[str] = None
    publishable_key: Optional[str] = None
    # Legacy alias kept for older clients
    stripe_publishable_key: Optional[str] = None
