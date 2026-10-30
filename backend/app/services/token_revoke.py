"""Refresh-token revocation store (logout)."""

from __future__ import annotations

import hashlib
from typing import Optional

from app.services.oauth_flow import MemoryOAuthTicketStore, OAuthTicketStore, _default_store

_PREFIX = "auth:revoked_refresh:"
_store: Optional[OAuthTicketStore] = None


def _store_client() -> OAuthTicketStore:
    global _store
    if _store is None:
        _store = _default_store()
    return _store


def reset_token_revoke_for_tests(store: Optional[OAuthTicketStore] = None) -> None:
    global _store
    _store = store or MemoryOAuthTicketStore()


def _key(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{_PREFIX}{digest}"


def revoke_refresh_token(token: str, *, ttl_seconds: int) -> None:
    if not token or ttl_seconds <= 0:
        return
    _store_client().put(_key(token), "1", ttl_seconds)


def is_refresh_token_revoked(token: str) -> bool:
    if not token:
        return False
    return _store_client().exists(_key(token))
