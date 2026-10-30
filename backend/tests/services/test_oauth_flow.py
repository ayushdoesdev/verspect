"""Regression tests for OAuth state CSRF protection and one-time login tickets."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app.services.oauth_flow import (
    MemoryOAuthTicketStore,
    OAuthFlowService,
    frontend_login_redirect,
    reset_oauth_flow_for_tests,
)


@pytest.fixture()
def flow() -> OAuthFlowService:
    return reset_oauth_flow_for_tests(MemoryOAuthTicketStore())


def test_state_is_single_use(flow: OAuthFlowService) -> None:
    state = flow.issue_state("github")
    flow.consume_state(state, provider="github")
    with pytest.raises(ValueError, match="Invalid or expired"):
        flow.consume_state(state, provider="github")


def test_state_rejects_missing_and_wrong_provider(flow: OAuthFlowService) -> None:
    with pytest.raises(ValueError, match="Missing"):
        flow.consume_state(None, provider="github")
    state = flow.issue_state("github")
    with pytest.raises(ValueError, match="provider mismatch"):
        flow.consume_state(state, provider="google")


def test_login_ticket_is_single_use(flow: OAuthFlowService) -> None:
    user_id = uuid4()
    code = flow.issue_login_ticket(user_id=user_id, provider="github")
    first = flow.consume_login_ticket(code)
    assert first.user_id == user_id
    assert first.provider == "github"
    with pytest.raises(ValueError, match="Invalid or expired"):
        flow.consume_login_ticket(code)


def test_concurrent_ticket_consume_only_one_wins(flow: OAuthFlowService) -> None:
    code = flow.issue_login_ticket(user_id=uuid4(), provider="google")
    results: list[bool] = []

    def attempt() -> None:
        try:
            flow.consume_login_ticket(code)
            results.append(True)
        except ValueError:
            results.append(False)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: attempt(), range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_frontend_redirect_never_contains_jwt_query_params() -> None:
    url = frontend_login_redirect("http://localhost:3000", "one-time-ticket-abc123xyz")
    assert url.startswith("http://localhost:3000/login/callback?")
    assert "code=one-time-ticket-abc123xyz" in url
    assert "access_token" not in url
    assert "refresh_token" not in url
