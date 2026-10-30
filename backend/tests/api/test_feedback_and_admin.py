"""Private Beta: feedback, contact, bootstrap admin, platform admin auth."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.deps import auth as auth_deps
from app.api.v1 import admin as admin_api
from app.api.v1 import contact as contact_api
from app.api.v1 import feedback as feedback_api
from app.api.v1.router import api_router
from app.core.rate_limit import (
    FixedWindowRateLimiter,
    contact_rate_limiter,
    feedback_rate_limiter,
)
from app.schemas.contact import ContactCreate
from app.schemas.feedback import FeedbackCreate
from app.services import bootstrap_admin as bootstrap_mod
from app.services.plans import PRICING_CATALOG


def test_feedback_and_admin_routers_registered() -> None:
    paths = {getattr(r, "path", "") for r in api_router.routes}
    assert any("/feedback" in p for p in paths)
    assert any("/admin/overview" in p for p in paths)
    assert any("/admin/feedback" in p for p in paths)
    assert any("/admin/analytics" in p for p in paths)
    assert any("/admin/contact-requests" in p for p in paths)
    assert any("/contact" in p for p in paths)


def test_require_platform_admin_checks_is_admin() -> None:
    src = inspect.getsource(auth_deps.require_platform_admin)
    assert "is_admin" in src
    assert "403" in src or "FORBIDDEN" in src


@pytest.mark.asyncio
async def test_platform_admin_allows_admin_user() -> None:
    admin = SimpleNamespace(is_admin=True, email="admin@verspect.dev")
    assert await auth_deps.require_platform_admin(admin) is admin


@pytest.mark.asyncio
async def test_platform_admin_rejects_non_admin_with_403() -> None:
    user = SimpleNamespace(is_admin=False, email="user@example.com")
    with pytest.raises(HTTPException) as exc:
        await auth_deps.require_platform_admin(user)
    assert exc.value.status_code == 403
    assert "admin" in exc.value.detail.lower()


def test_admin_routes_depend_on_platform_admin() -> None:
    src = inspect.getsource(admin_api)
    assert "PlatformAdmin" in src
    assert "require_platform_admin" in inspect.getsource(auth_deps)
    assert "AdminOverview" in src
    assert "average_simulation_duration_seconds" in src
    assert "workers" in src
    assert "redis" in src
    assert "database" in src


def test_feedback_create_validates_email_and_category() -> None:
    ok = FeedbackCreate(
        category="bug_report",
        title="Scan stuck",
        description="Scan stayed queued for several minutes after Redis restart.",
        email="user@example.com",
        priority="high",
    )
    assert ok.category == "bug_report"
    assert ok.priority == "high"

    with pytest.raises(ValidationError):
        FeedbackCreate(
            category="bug_report",
            title="x",
            description="too short",
            email="not-an-email",
        )

    with pytest.raises(ValidationError):
        FeedbackCreate(
            category="bug_report",
            title="Valid title here",
            description="Long enough description for the form.",
            email="user@example.com",
            priority="urgent",  # type: ignore[arg-type]
        )


def test_contact_create_validates_email_and_message() -> None:
    ok = ContactCreate(
        name="Ada Lovelace",
        company="Analytical Engines",
        email="ada@example.com",
        team_size="11-50",
        message="We would like a demo of Verspect for our platform team.",
    )
    assert ok.email == "ada@example.com"

    with pytest.raises(ValidationError):
        ContactCreate(
            name="Ada",
            email="not-an-email",
            message="Please schedule a demo for our engineering team.",
        )

    with pytest.raises(ValidationError):
        ContactCreate(
            name="Ada",
            email="ada@example.com",
            message="short",
        )


def test_feedback_rate_limiter_blocks() -> None:
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    assert feedback_rate_limiter.limit == 5


def test_contact_rate_limiter_configured() -> None:
    assert contact_rate_limiter.limit == 5
    src = inspect.getsource(contact_api.submit_contact_request)
    assert "contact_rate_limiter" in src
    assert "429" in src or "TOO_MANY_REQUESTS" in src


def test_feedback_endpoint_uses_rate_limiter() -> None:
    src = inspect.getsource(feedback_api.submit_feedback)
    assert "feedback_rate_limiter" in src
    assert "429" in src or "TOO_MANY_REQUESTS" in src


def test_evaluation_catalog_messaging() -> None:
    free = next(p for p in PRICING_CATALOG if p["id"] == "free")
    assert free["name"] == "Evaluation Plan"
    assert "evaluating Verspect" in free["tagline"]
    assert free["price_label"] != "Free"
    assert any("AI-powered" in h or "paid plans" in h for h in free["highlights"])


def test_admin_overview_and_analytics_exist() -> None:
    assert hasattr(admin_api, "admin_overview")
    assert hasattr(admin_api, "admin_analytics")
    assert hasattr(admin_api, "admin_list_feedback")
    assert hasattr(admin_api, "admin_update_feedback_status")
    assert hasattr(admin_api, "admin_list_contact_requests")
    assert hasattr(admin_api, "admin_list_users")
    assert hasattr(admin_api, "AdminOverview")
    fields = set(admin_api.AdminOverview.model_fields)
    for required in (
        "total_users",
        "verified_users",
        "organizations",
        "repositories",
        "repository_scans",
        "ai_advisor_jobs",
        "upgrade_simulations",
        "daily_signups",
        "daily_imports",
        "daily_scans",
        "failed_jobs",
        "workers",
        "redis",
        "database",
    ):
        assert required in fields


@pytest.mark.asyncio
async def test_bootstrap_admin_skips_production_async() -> None:
    settings = SimpleNamespace(
        app_env="production",
        bootstrap_admin_email="admin@verspect.dev",
        bootstrap_admin_password="Verspect@2026!",
        bootstrap_admin_name="Verspect Admin",
    )
    with patch.object(bootstrap_mod, "get_settings", return_value=settings):
        with patch.object(bootstrap_mod, "AsyncSessionLocal") as session_factory:
            await bootstrap_mod.ensure_bootstrap_admin()
            session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_bootstrap_admin_promotes_existing_user() -> None:
    settings = SimpleNamespace(
        app_env="development",
        bootstrap_admin_email="admin@verspect.dev",
        bootstrap_admin_password="Verspect@2026!",
        bootstrap_admin_name="Verspect Admin",
    )
    existing = SimpleNamespace(
        is_admin=False,
        email_verified=False,
        is_active=False,
        email="admin@verspect.dev",
    )
    result_admin_count = MagicMock()
    result_admin_count.scalar_one.return_value = 0
    result_existing = MagicMock()
    result_existing.scalar_one_or_none.return_value = existing

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[result_admin_count, result_existing])
    db.commit = AsyncMock()

    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = db
    session_cm.__aexit__.return_value = None

    with patch.object(bootstrap_mod, "get_settings", return_value=settings):
        with patch.object(bootstrap_mod, "AsyncSessionLocal", return_value=session_cm):
            await bootstrap_mod.ensure_bootstrap_admin()

    assert existing.is_admin is True
    assert existing.email_verified is True
    assert existing.is_active is True
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_bootstrap_admin_creates_when_none_exist() -> None:
    settings = SimpleNamespace(
        app_env="beta",
        bootstrap_admin_email="admin@verspect.dev",
        bootstrap_admin_password="Verspect@2026!",
        bootstrap_admin_name="Verspect Admin",
    )
    result_admin_count = MagicMock()
    result_admin_count.scalar_one.return_value = 0
    result_existing = MagicMock()
    result_existing.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[result_admin_count, result_existing])
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = db
    session_cm.__aexit__.return_value = None

    with patch.object(bootstrap_mod, "get_settings", return_value=settings):
        with patch.object(bootstrap_mod, "AsyncSessionLocal", return_value=session_cm):
            with patch.object(bootstrap_mod, "hash_password", return_value="hashed") as hp:
                with patch.object(
                    bootstrap_mod, "ensure_personal_organization", new=AsyncMock()
                ) as org:
                    await bootstrap_mod.ensure_bootstrap_admin()
                    hp.assert_called_once_with("Verspect@2026!")
                    org.assert_awaited()

    assert db.add.called
    created = db.add.call_args[0][0]
    assert created.email == "admin@verspect.dev"
    assert created.is_admin is True
    assert created.email_verified is True
    assert created.is_active is True
    assert created.password_hash == "hashed"
    db.commit.assert_awaited()


def test_bootstrap_defaults_match_spec() -> None:
    assert bootstrap_mod.DEFAULT_BOOTSTRAP_EMAIL == "admin@verspect.dev"
    assert bootstrap_mod.DEFAULT_BOOTSTRAP_PASSWORD == "Verspect@2026!"
    assert bootstrap_mod.DEFAULT_BOOTSTRAP_NAME == "Verspect Admin"
