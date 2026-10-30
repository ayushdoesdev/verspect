"""Groq provider — OpenAI-compatible Chat Completions via httpx (no openai SDK)."""

from __future__ import annotations

import time
from typing import Optional

import httpx

from app.ai.exceptions import AIProviderError, AIProviderUnavailable
from app.ai.providers.base import AICompletionResult, AIProvider
from app.ai.schemas import CompletionMeta


class GroqProvider(AIProvider):
    name = "groq"
    default_model = "llama-3.3-70b-versatile"
    BASE_URL = "https://api.groq.com/openai/v1"

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
            raise AIProviderUnavailable(self.name, "GROQ_API_KEY not configured")
        if stream:
            raise NotImplementedError("Groq streaming not enabled yet")

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
                    f"{self.BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
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
