"""Regression H12: auth endpoints are rate limited."""

from __future__ import annotations

from app.core.rate_limit import FixedWindowRateLimiter


def test_fixed_window_rate_limiter_blocks_after_limit() -> None:
    limiter = FixedWindowRateLimiter(limit=3, window_seconds=60)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False
