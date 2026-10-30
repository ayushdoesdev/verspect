"""OpenRouter provider — OpenAI-compatible Chat Completions via httpx (no openai SDK)."""

from __future__ import annotations

import time
from typing import Optional

import httpx

from app.ai.exceptions import AIProviderError, AIProviderUnavailable
from app.ai.providers.base import AICompletionResult, AIProvider
from app.ai.schemas import CompletionMeta
from app.core.config import get_settings


class OpenRouterProvider(AIProvider):
    name = "openrouter"
    default_model = "openai/gpt-4o-mini"

    def __init__(self, *, base_url: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        settings = get_settings()
        self.base_url = (base_url or settings.openrouter_base_url or "https://openrouter.ai/api/v1").rstrip(
            "/"
        )
        self.app_url = settings.app_url or "http://localhost:3000"
        self.app_name = settings.app_name or "Dependency Intelligence"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        json_mode: bool = True,
        think: Optional[bool] = None,
    ) -> AICompletionResult:
        if not self.is_available():
            raise AIProviderUnavailable(self.name, "OPENROUTER_API_KEY not configured")
        if stream:
            raise NotImplementedError("OpenRouter streaming not enabled yet")

        started = time.perf_counter()
        payload: dict = {
            "model": self.model,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": self.app_url,
                        "X-Title": self.app_name,
                    },
                    json=payload,
                )
            if resp.status_code >= 400:
                raise AIProviderError(self.name, f"HTTP {resp.status_code}: {resp.text[:400]}")
            data = resp.json()
            text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
        except AIProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(self.name, str(exc), cause=exc) from exc

        usage = data.get("usage") or {}
        latency = (time.perf_counter() - started) * 1000
        return AICompletionResult(
            text,
            meta=CompletionMeta(
                provider=self.name,
                model=self.model,
                latency_ms=round(latency, 1),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
            ),
            raw=data,
        )
