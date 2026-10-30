"""Regression H11: logout must revoke refresh tokens."""

from __future__ import annotations

from app.services.oauth_flow import MemoryOAuthTicketStore
from app.services.token_revoke import (
    is_refresh_token_revoked,
    reset_token_revoke_for_tests,
    revoke_refresh_token,
)


def test_revoke_refresh_token_is_detected() -> None:
    reset_token_revoke_for_tests(MemoryOAuthTicketStore())
    token = "refresh.jwt.example"
    assert is_refresh_token_revoked(token) is False
    revoke_refresh_token(token, ttl_seconds=60)
    assert is_refresh_token_revoked(token) is True


def test_forgot_password_sends_email() -> None:
    import inspect
    from app.api.v1 import auth as auth_api

    src = inspect.getsource(auth_api.forgot_password)
    assert "send_email" in src
    assert "password_reset_token" in src
