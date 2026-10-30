"""AI response cache — keyed by provider, model, prompt hash, and entity ids."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AICache:
    """Redis-backed cache for structured AI responses."""

    PREFIX = "ai:v1:"

    def __init__(self, ttl: Optional[int] = None) -> None:
        settings = get_settings()
        self.ttl = ttl if ttl is not None else settings.ai_cache_ttl_seconds
        self._client: Any = None
        try:
            import redis

            self._client = redis.from_url(settings.redis_url, decode_responses=True)
            self._client.ping()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai_cache_redis_unavailable", error=str(exc))
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    @staticmethod
    def prompt_hash(system: str, user: str) -> str:
        raw = f"{system}\n---\n{user}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def make_key(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        system: str,
        user: str,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> str:
        ph = self.prompt_hash(system, user)
        parts = [
            provider or "unknown",
            model or "unknown",
            operation or "complete",
            ph,
            repository_id or "-",
            dependency_id or "-",
            version or "-",
        ]
        return self.PREFIX + hashlib.sha256("|".join(parts).encode()).hexdigest()[:48]

    def get(self, key: str) -> Optional[Any]:
        if not self._client:
            return None
        try:
            raw = self._client.get(key)
            if raw is None:
                logger.info("ai_cache_miss", key=key[:24])
                return None
            logger.info("ai_cache_hit", key=key[:24])
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.debug("ai_cache_get_failed", error=str(exc))
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if not self._client:
            return
        try:
            self._client.setex(key, ttl or self.ttl, json.dumps(value, default=str))
        except Exception as exc:  # noqa: BLE001
            logger.debug("ai_cache_set_failed", error=str(exc))
