"""Plan definitions and feature limit enforcement.

Commercial launch pricing (source of truth):

  Evaluation (plan id: free) — 7-day no-CC evaluation · 1 repo · Upgrade Simulator · No AI
  Starter   — $19/mo · individuals · 10 repos · Upgrade Simulator · No AI Migration
  Pro       — $39/mo · unlimited repos/scans · API · scheduled · No AI Migration
  Team      — $59/user/mo · orgs · RBAC · audit · AI Migration Assistant
  Enterprise — custom · SSO · SCIM · private AI · SLA

Upgrade Simulator (analysis) requires an active evaluation or paid plan.
AI Migration Assistant (code generation) is Team / Enterprise only.
Never merge these products.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException, status


FEATURE_AI = "ai"
FEATURE_AI_MIGRATION = "ai_migration_assistant"
FEATURE_UPGRADE_SIMULATOR = "upgrade_simulator"
PAID_PLANS = frozenset({"starter", "pro", "team", "enterprise"})
TEAM_PLANS = frozenset({"team", "enterprise"})
CHECKOUT_PLANS = frozenset({"starter", "pro", "team"})
TRIAL_DAYS = 7


@dataclass(frozen=True)
class PlanLimits:
    plan: str
    max_users: Optional[int]  # None = unlimited / seat-based
    max_repositories: Optional[int]
    monthly_scan_limit: Optional[int]  # None = unlimited
    upgrade_simulator: bool
    ai_enabled: bool  # AI Upgrade Advisor / dependency summaries
    ai_migration_assistant: bool
    teams_enabled: bool
    rbac: bool
    scheduled_scans: bool
    api_access: bool
    webhooks: bool
    priority_scans: bool
    export_reports: bool
    advanced_reports: bool
    slack_integration: bool
    sso_ready: bool
    scim: bool
    audit_logs: bool
    private_ai: bool
    display_name: str


PLANS: dict[str, PlanLimits] = {
    "free": PlanLimits(
        plan="free",
        max_users=1,
        max_repositories=1,
        monthly_scan_limit=20,
        upgrade_simulator=True,
        ai_enabled=False,
        ai_migration_assistant=False,
        teams_enabled=False,
        rbac=False,
        scheduled_scans=False,
        api_access=False,
        webhooks=False,
        priority_scans=False,
        export_reports=False,
        advanced_reports=False,
        slack_integration=False,
        sso_ready=False,
        scim=False,
        audit_logs=False,
        private_ai=False,
        display_name="Evaluation Plan",
    ),
    "starter": PlanLimits(
        plan="starter",
        max_users=1,
        max_repositories=10,
        monthly_scan_limit=100,
        upgrade_simulator=True,
        ai_enabled=False,
        ai_migration_assistant=False,
        teams_enabled=False,
        rbac=False,
        scheduled_scans=False,
        api_access=False,
        webhooks=False,
        priority_scans=False,
        export_reports=True,
        advanced_reports=False,
        slack_integration=False,
        sso_ready=False,
        scim=False,
        audit_logs=False,
        private_ai=False,
        display_name="Starter",
    ),
    "pro": PlanLimits(
        plan="pro",
        max_users=1,
        max_repositories=None,
        monthly_scan_limit=None,
        upgrade_simulator=True,
        ai_enabled=True,
        ai_migration_assistant=False,
        teams_enabled=False,
        rbac=False,
        scheduled_scans=True,
        api_access=True,
        webhooks=True,
        priority_scans=True,
        export_reports=True,
        advanced_reports=True,
        slack_integration=False,
        sso_ready=False,
        scim=False,
        audit_logs=False,
        private_ai=False,
        display_name="Pro",
    ),
    "team": PlanLimits(
        plan="team",
        max_users=None,  # billed per seat
        max_repositories=None,
        monthly_scan_limit=None,
        upgrade_simulator=True,
        ai_enabled=True,
        ai_migration_assistant=True,
        teams_enabled=True,
        rbac=True,
        scheduled_scans=True,
        api_access=True,
        webhooks=True,
        priority_scans=True,
        export_reports=True,
        advanced_reports=True,
        slack_integration=True,
        sso_ready=False,
        scim=False,
        audit_logs=True,
        private_ai=False,
        display_name="Team",
    ),
    "enterprise": PlanLimits(
        plan="enterprise",
        max_users=None,
        max_repositories=None,
        monthly_scan_limit=None,
        upgrade_simulator=True,
        ai_enabled=True,
        ai_migration_assistant=True,
        teams_enabled=True,
        rbac=True,
        scheduled_scans=True,
        api_access=True,
        webhooks=True,
        priority_scans=True,
        export_reports=True,
        advanced_reports=True,
        slack_integration=True,
        sso_ready=True,
        scim=True,
        audit_logs=True,
        private_ai=True,
        display_name="Enterprise",
    ),
}


def get_plan_limits(plan: str) -> PlanLimits:
    return PLANS.get((plan or "free").lower(), PLANS["free"])


def require_feature(plan: str, *, feature: str) -> PlanLimits:
    limits = get_plan_limits(plan)
    mapping = {
        FEATURE_AI: limits.ai_enabled,
        FEATURE_AI_MIGRATION: limits.ai_migration_assistant,
        FEATURE_UPGRADE_SIMULATOR: limits.upgrade_simulator,
        "ai": limits.ai_enabled,
        "ai_migration_assistant": limits.ai_migration_assistant,
        "upgrade_simulator": limits.upgrade_simulator,
        "teams": limits.teams_enabled,
        "rbac": limits.rbac,
        "scheduled_scans": limits.scheduled_scans,
        "api": limits.api_access,
        "webhooks": limits.webhooks,
        "priority_scans": limits.priority_scans,
        "export_reports": limits.export_reports,
        "slack": limits.slack_integration,
        "sso": limits.sso_ready,
        "scim": limits.scim,
        "audit_logs": limits.audit_logs,
    }
    if feature not in mapping:
        return limits
    if not mapping[feature]:
        status_code = (
            status.HTTP_403_FORBIDDEN
            if feature in {FEATURE_AI_MIGRATION, "ai_migration_assistant"}
            else status.HTTP_402_PAYMENT_REQUIRED
        )
        if feature in {FEATURE_AI_MIGRATION, "ai_migration_assistant"}:
            message = "AI Migration Assistant requires a Team or Enterprise subscription."
        elif feature in {FEATURE_UPGRADE_SIMULATOR, "upgrade_simulator"}:
            message = "Upgrade Simulator is unavailable on your current plan."
        elif feature in {FEATURE_AI, "ai"}:
            message = (
                f"AI Upgrade Advisor requires a Pro subscription or higher. "
                f"Current plan: {limits.display_name}."
            )
        else:
            message = (
                f"The '{feature}' feature requires a higher plan. "
                f"Current plan: {limits.display_name}."
            )
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": "premium_required" if status_code == 403 else "plan_limit",
                "feature": feature,
                "plan": limits.plan,
                "message": message,
            },
        )
    return limits


def assert_repo_limit(plan: str, current_count: int, adding: int = 1) -> None:
    limits = get_plan_limits(plan)
    if limits.max_repositories is None:
        return
    if current_count + adding > limits.max_repositories:
        upgrade_hint = (
            "Upgrade to Starter for 10 repositories, or Pro for unlimited."
            if limits.plan == "free"
            else "Upgrade to Pro for unlimited repositories."
            if limits.plan == "starter"
            else "Contact support if you need a higher repository limit."
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "plan_limit",
                "feature": "repositories",
                "plan": limits.plan,
                "limit": limits.max_repositories,
                "message": (
                    f"{limits.display_name} plan allows {limits.max_repositories} "
                    f"repositor{'y' if limits.max_repositories == 1 else 'ies'}. "
                    f"{upgrade_hint}"
                ),
            },
        )


def assert_seat_limit(plan: str, current_members: int, adding: int = 1) -> None:
    limits = get_plan_limits(plan)
    if limits.max_users is None:
        return
    if current_members + adding > limits.max_users:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "plan_limit",
                "feature": "seats",
                "plan": limits.plan,
                "limit": limits.max_users,
                "message": (
                    f"{limits.display_name} plan allows {limits.max_users} user(s). "
                    "Upgrade to Team for multi-seat collaboration."
                ),
            },
        )


def assert_scan_limit(plan: str, scans_this_month: int) -> None:
    limits = get_plan_limits(plan)
    if limits.monthly_scan_limit is None:
        return
    if scans_this_month >= limits.monthly_scan_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "plan_limit",
                "feature": "scans",
                "plan": limits.plan,
                "limit": limits.monthly_scan_limit,
                "message": (
                    f"{limits.display_name} plan allows {limits.monthly_scan_limit} "
                    "scans per month. Upgrade to Pro for unlimited scans."
                    if limits.plan in {"free", "starter"}
                    else (
                        f"{limits.display_name} plan allows {limits.monthly_scan_limit} "
                        "scans per month."
                    )
                ),
            },
        )


PRICING_CATALOG: list[dict[str, Any]] = [
    {
        "id": "free",
        "name": "Evaluation Plan",
        "tagline": (
            "Perfect for evaluating Verspect on your repositories "
            "before upgrading to a paid plan."
        ),
        "monthly_price": 0,
        "yearly_price": 0,
        "cta": "Start Evaluation",
        "badge": None,
        "highlighted": False,
        "price_label": "Evaluation",
        "billing_note": "7 days · no credit card · intended for evaluation",
        "highlights": [
            "Evaluate Verspect on your repositories",
            "1 repository · 1 user",
            "Limited monthly scans",
            "Repository Scan & Sync",
            "Dependency Graph & Analysis",
            "Version & Security Analysis",
            "Upgrade Simulator (analysis)",
            "AI-powered capabilities available on eligible paid plans",
        ],
        "not_included": [
            "AI Upgrade Advisor (eligible paid plans)",
            "AI Migration Assistant",
            "API · Scheduled Scans",
            "Organizations · Teams · RBAC",
            "Audit Logs",
        ],
    },
    {
        "id": "starter",
        "name": "Starter",
        "tagline": "For individual developers",
        "monthly_price": 19,
        "yearly_price": 190,
        "cta": "Upgrade to Starter",
        "badge": "Most Popular",
        "highlighted": True,
        "price_label": "$19",
        "billing_note": "per month · billed monthly",
        "highlights": [
            "Up to 10 repositories · 1 user",
            "Repository Scan & Sync",
            "Dependency Graph",
            "Version & Security Analysis",
            "Upgrade Simulator",
            "Background Jobs",
            "Export Reports",
            "Email Support",
        ],
        "not_included": [
            "API",
            "Scheduled Scans",
            "AI Migration Assistant",
            "Organizations · Teams · RBAC",
            "Audit Logs",
        ],
    },
    {
        "id": "pro",
        "name": "Pro",
        "tagline": "Scale your dependency ops",
        "monthly_price": 39,
        "yearly_price": 390,
        "cta": "Upgrade to Pro",
        "badge": None,
        "highlighted": False,
        "price_label": "$39",
        "billing_note": "per month · billed monthly",
        "highlights": [
            "Everything in Starter",
            "Unlimited repositories & scans",
            "GitHub inbound webhooks",
            "Scheduled Scans",
            "Priority processing",
            "Advanced Reports",
            "AI Upgrade Advisor",
        ],
        "not_included": [
            "AI Migration Assistant",
            "Organizations · Teams · RBAC",
            "Audit Logs",
        ],
    },
    {
        "id": "team",
        "name": "Team",
        "tagline": "Best for Teams",
        "monthly_price": 59,
        "yearly_price": 590,
        "cta": "Upgrade to Team",
        "badge": "Best for Teams",
        "highlighted": True,
        "price_label": "$59",
        "billing_note": "per user / month · billed monthly",
        "per_seat": True,
        "highlights": [
            "Everything in Pro",
            "Organizations & repository sharing",
            "Multiple users · RBAC",
            "Audit Logs · Team Dashboard",
            "Activity History",
            "✨ AI Migration Assistant",
            "Exact code replacements & AI patches",
            "Line-by-line migration guidance",
        ],
        "not_included": [],
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "tagline": "Global scale & control",
        "monthly_price": None,
        "yearly_price": None,
        "cta": "Contact Sales",
        "badge": None,
        "highlighted": False,
        "price_label": "Custom",
        "billing_note": "SSO · SCIM · private deployment",
        "highlights": [
            "Everything in Team",
            "SSO & SCIM",
            "Self-hosted / dedicated infrastructure",
            "Private AI",
            "SLA & dedicated support",
        ],
        "not_included": [],
    },
]


def _row(
    feature: str,
    *,
    free: bool,
    starter: bool,
    pro: bool,
    team: bool,
    enterprise: bool,
    premium: bool = False,
    exclusive: str | None = None,
) -> dict[str, Any]:
    return {
        "feature": feature,
        "free": free,
        "starter": starter,
        "pro": pro,
        "team": team,
        "enterprise": enterprise,
        "premium": premium,
        "exclusive": exclusive,
    }


FEATURE_COMPARISON: list[dict[str, Any]] = [
    _row("Repository Scanning", free=True, starter=True, pro=True, team=True, enterprise=True),
    _row("Repository Sync", free=True, starter=True, pro=True, team=True, enterprise=True),
    _row("Dependency Analysis", free=True, starter=True, pro=True, team=True, enterprise=True),
    _row("Dependency Graph", free=True, starter=True, pro=True, team=True, enterprise=True),
    _row("Version Analysis", free=True, starter=True, pro=True, team=True, enterprise=True),
    _row("Security Analysis / CVEs", free=True, starter=True, pro=True, team=True, enterprise=True),
    _row("Upgrade Simulator (analysis)", free=True, starter=True, pro=True, team=True, enterprise=True),
    _row("Background Jobs", free=True, starter=True, pro=True, team=True, enterprise=True),
    _row("Export Reports", free=False, starter=True, pro=True, team=True, enterprise=True),
    _row("Unlimited repositories", free=False, starter=False, pro=True, team=True, enterprise=True),
    _row("Unlimited scans", free=False, starter=False, pro=True, team=True, enterprise=True),
    _row("GitHub inbound webhooks", free=False, starter=False, pro=True, team=True, enterprise=True),
    _row("Scheduled Scans", free=False, starter=False, pro=True, team=True, enterprise=True),
    _row("Priority Queue", free=False, starter=False, pro=True, team=True, enterprise=True),
    _row("AI Upgrade Advisor", free=False, starter=False, pro=True, team=True, enterprise=True),
    _row(
        "AI Migration Assistant",
        free=False,
        starter=False,
        pro=False,
        team=True,
        enterprise=True,
        premium=True,
        exclusive="team",
    ),
    _row(
        "Exact Code Replacements & Patches",
        free=False,
        starter=False,
        pro=False,
        team=True,
        enterprise=True,
        premium=True,
        exclusive="team",
    ),
    _row("Organizations & Teams", free=False, starter=False, pro=False, team=True, enterprise=True),
    _row("RBAC", free=False, starter=False, pro=False, team=True, enterprise=True),
    _row("Audit Logs", free=False, starter=False, pro=False, team=True, enterprise=True),
    _row("SSO / SCIM", free=False, starter=False, pro=False, team=False, enterprise=True),
    _row("Private AI / Self-hosted", free=False, starter=False, pro=False, team=False, enterprise=True),
]
