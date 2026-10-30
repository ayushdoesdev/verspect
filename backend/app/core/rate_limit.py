"""Simple fixed-window rate limiter for sensitive auth endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque


class FixedWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True


# Auth abuse protection: 30 requests / minute / IP for /api/v1/auth/*
auth_rate_limiter = FixedWindowRateLimiter(limit=30, window_seconds=60)

# Feedback spam protection: 5 submissions / minute / IP
feedback_rate_limiter = FixedWindowRateLimiter(limit=5, window_seconds=60)

# Contact / demo request protection: 5 submissions / minute / IP
contact_rate_limiter = FixedWindowRateLimiter(limit=5, window_seconds=60)
