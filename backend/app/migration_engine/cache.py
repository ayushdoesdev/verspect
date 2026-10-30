"""Cache helpers for migration engine — Redis + content hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

DEFAULT_TTL = 60 * 60 * 24 * 7  # 7 days


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def rule_identity_key(
    normalized_name: str,
    from_version: str,
    to_version: str,
    symbol: str,
    kind: str,
) -> str:
    raw = f"{normalized_name}|{from_version}|{to_version}|{symbol}|{kind}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


class MigrationCache:
    """Thin Redis cache for docs, AI extractions, and reports."""

    def __init__(self) -> None:
        self._client: Any = None
        try:
            import redis

            self._client = redis.from_url(settings.redis_url, decode_responses=True)
            self._client.ping()
        except Exception as exc:
            logger.warning("migration_cache_redis_unavailable", error=str(exc))
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def get_json(self, key: str) -> Optional[Any]:
        if not self._client:
            return None
        try:
            raw = self._client.get(f"mig:{key}")
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
        if not self._client:
            return
        try:
            self._client.setex(f"mig:{key}", ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.debug("migration_cache_set_failed", error=str(exc))

    def get_text(self, key: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            return self._client.get(f"mig:{key}")
        except Exception:
            return None

    def set_text(self, key: str, value: str, ttl: int = DEFAULT_TTL) -> None:
        if not self._client:
            return
        try:
            self._client.setex(f"mig:{key}", ttl, value)
        except Exception:
            pass

    def docs_key(self, url: str) -> str:
        return f"docs:{content_hash(url)}"

    def rules_key(self, normalized: str, from_v: str, to_v: str) -> str:
        return f"rules:{normalized}:{from_v}:{to_v}"

    def report_key(self, dep_id: str, from_v: str, to_v: str, usage_fp: str) -> str:
        return f"report:{dep_id}:{from_v}:{to_v}:{usage_fp}"
