"""OAuth CSRF state + one-time login tickets.

Never put JWTs in redirect URLs. Callbacks mint a short-lived, single-use
ticket; the SPA exchanges it over POST for access/refresh tokens.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

STATE_TTL_SECONDS = 600
TICKET_TTL_SECONDS = 120


class OAuthTicketStore(Protocol):
    def put(self, key: str, value: str, ttl_seconds: int) -> None: ...

    def pop(self, key: str) -> Optional[str]: ...

    def exists(self, key: str) -> bool: ...


class MemoryOAuthTicketStore:
    """Process-local store for tests. Not shared across workers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, tuple[str, float]] = {}

    def put(self, key: str, value: str, ttl_seconds: int) -> None:
        with self._lock:
            self._items[key] = (value, time.monotonic() + ttl_seconds)

    def pop(self, key: str) -> Optional[str]:
        with self._lock:
            item = self._items.pop(key, None)
            if item is None:
                return None
            value, expires = item
            if time.monotonic() > expires:
                return None
            return value

    def exists(self, key: str) -> bool:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return False
            _, expires = item
            if time.monotonic() > expires:
                self._items.pop(key, None)
                return False
            return True

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class RedisOAuthTicketStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def put(self, key: str, value: str, ttl_seconds: int) -> None:
        self._client.setex(key, ttl_seconds, value)

    def pop(self, key: str) -> Optional[str]:
        # GETDEL when available (Redis 6.2+); otherwise GET + DELETE.
        try:
            value = self._client.getdel(key)
        except Exception:  # noqa: BLE001
            pipe = self._client.pipeline()
            pipe.get(key)
            pipe.delete(key)
            value, _ = pipe.execute()
        if value is None:
            return None
        return value if isinstance(value, str) else value.decode("utf-8")

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))


@dataclass(frozen=True)
class LoginTicketPayload:
    user_id: UUID
    provider: str


class OAuthFlowService:
    STATE_PREFIX = "oauth:state:"
    TICKET_PREFIX = "oauth:ticket:"

    def __init__(self, store: Optional[OAuthTicketStore] = None) -> None:
        self._store = store if store is not None else _default_store()

    def issue_state(self, provider: str) -> str:
        state = secrets.token_urlsafe(32)
        payload = json.dumps({"provider": provider})
        self._store.put(f"{self.STATE_PREFIX}{state}", payload, STATE_TTL_SECONDS)
        return state

    def consume_state(self, state: str | None, *, provider: str) -> None:
        if not state:
            raise ValueError("Missing OAuth state")
        raw = self._store.pop(f"{self.STATE_PREFIX}{state}")
        if raw is None:
            raise ValueError("Invalid or expired OAuth state")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid OAuth state payload") from exc
        if data.get("provider") != provider:
            raise ValueError("OAuth state provider mismatch")

    def issue_login_ticket(self, *, user_id: UUID, provider: str) -> str:
        code = secrets.token_urlsafe(32)
        payload = json.dumps({"user_id": str(user_id), "provider": provider})
        self._store.put(f"{self.TICKET_PREFIX}{code}", payload, TICKET_TTL_SECONDS)
        return code

    def consume_login_ticket(self, code: str | None) -> LoginTicketPayload:
        if not code:
            raise ValueError("Missing login code")
        raw = self._store.pop(f"{self.TICKET_PREFIX}{code}")
        if raw is None:
            raise ValueError("Invalid or expired login code")
        try:
            data = json.loads(raw)
            return LoginTicketPayload(
                user_id=UUID(data["user_id"]),
                provider=str(data.get("provider") or "unknown"),
            )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid login code payload") from exc


_memory_fallback = MemoryOAuthTicketStore()
_service: Optional[OAuthFlowService] = None


def _default_store() -> OAuthTicketStore:
    settings = get_settings()
    try:
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return RedisOAuthTicketStore(client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("oauth_flow_redis_unavailable_using_memory", error=str(exc))
        return _memory_fallback


def get_oauth_flow() -> OAuthFlowService:
    global _service
    if _service is None:
        _service = OAuthFlowService()
    return _service


def reset_oauth_flow_for_tests(store: Optional[OAuthTicketStore] = None) -> OAuthFlowService:
    """Test helper — inject a fresh store and reset the singleton."""
    global _service
    _service = OAuthFlowService(store=store or MemoryOAuthTicketStore())
    return _service


def frontend_login_redirect(app_url: str, login_code: str) -> str:
    """Build the SPA callback URL. Must never include JWT query params."""
    from urllib.parse import urlencode

    return f"{app_url.rstrip('/')}/login/callback?{urlencode({'code': login_code})}"
