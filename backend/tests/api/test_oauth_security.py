"""Security regression: OAuth callbacks must not put JWTs in redirect URLs."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.schemas.user import TokenResponse, UserResponse
from app.services.oauth_flow import MemoryOAuthTicketStore, reset_oauth_flow_for_tests

client = TestClient(app)


def _fake_user_response(user_id=None) -> UserResponse:
    user_id = user_id or uuid4()
    now = datetime.now(timezone.utc)
    return UserResponse(
        id=user_id,
        github_login="oauth-tester",
        email="oauth@example.com",
        name="OAuth Tester",
        avatar_url=None,
        github_id=1,
        google_id=None,
        auth_provider="github",
        email_verified=True,
        is_active=True,
        is_admin=False,
        onboarding_completed=True,
        active_organization_id=None,
        email_notifications=True,
        slack_notifications=False,
        slack_webhook_url=None,
        notify_on_critical_cve=True,
        notify_on_major_release=True,
        notify_on_license_violation=True,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def _fake_token_response(user_id=None) -> TokenResponse:
    user = _fake_user_response(user_id)
    return TokenResponse(
        access_token="ACCESS.JWT.VALUE",
        refresh_token="REFRESH.JWT.VALUE",
        expires_in=3600,
        user=user,
    )


def test_github_callback_redirect_has_code_not_tokens() -> None:
    flow = reset_oauth_flow_for_tests(MemoryOAuthTicketStore())
    state = flow.issue_state("github")
    tokens = _fake_token_response()

    with patch(
        "app.api.v1.auth.github_auth_service.authenticate_with_code",
        new=AsyncMock(return_value=tokens),
    ):
        response = client.get(
            f"/api/v1/auth/github/callback?code=gh-oauth-code&state={state}",
            follow_redirects=False,
        )

    assert response.status_code == 302
    location = response.headers["location"]
    assert "/login/callback?" in location
    assert "code=" in location
    assert "access_token" not in location
    assert "refresh_token" not in location
    assert "ACCESS.JWT" not in location
    assert "REFRESH.JWT" not in location


def test_github_callback_rejects_invalid_state() -> None:
    reset_oauth_flow_for_tests(MemoryOAuthTicketStore())
    response = client.get(
        "/api/v1/auth/github/callback?code=gh-oauth-code&state=forged-state",
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert "/login?" in location
    assert "error=" in location
    assert "access_token" not in location


def test_github_auth_url_persists_validatable_state() -> None:
    flow = reset_oauth_flow_for_tests(MemoryOAuthTicketStore())
    with patch(
        "app.api.v1.auth.github_auth_service.get_authorization_url",
        side_effect=lambda state=None: (
            f"https://github.com/login/oauth/authorize?state={state}",
            state,
        ),
    ):
        response = client.get("/api/v1/auth/github/url")

    assert response.status_code == 200
    body = response.json()
    assert body["state"]
    assert body["state"] in body["authorization_url"]
    flow.consume_state(body["state"], provider="github")


def test_oauth_exchange_is_single_use() -> None:
    flow = reset_oauth_flow_for_tests(MemoryOAuthTicketStore())
    user_id = uuid4()
    code = flow.issue_login_ticket(user_id=user_id, provider="github")
    now = datetime.now(timezone.utc)

    fake_user = SimpleNamespace(
        id=user_id,
        github_login="oauth-tester",
        email="oauth@example.com",
        name="OAuth Tester",
        avatar_url=None,
        github_id=1,
        google_id=None,
        auth_provider="github",
        email_verified=True,
        is_active=True,
        is_admin=False,
        onboarding_completed=True,
        active_organization_id=None,
        email_notifications=True,
        slack_notifications=False,
        slack_webhook_url=None,
        notify_on_critical_cve=True,
        notify_on_major_release=True,
        notify_on_license_violation=True,
        last_login_at=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )

    class _Result:
        def scalar_one_or_none(self):
            return fake_user

    async def _override_db():
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_Result())
        yield session

    app.dependency_overrides[get_db] = _override_db
    try:
        with patch("app.api.v1.auth.create_access_token", return_value="access"):
            with patch("app.api.v1.auth.create_refresh_token", return_value="refresh"):
                first = client.post("/api/v1/auth/oauth/exchange", json={"code": code})
                assert first.status_code == 200, first.text
                assert first.json()["access_token"] == "access"
                second = client.post("/api/v1/auth/oauth/exchange", json={"code": code})
                assert second.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)
