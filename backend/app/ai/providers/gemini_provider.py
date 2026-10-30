"""Gemini provider — uses Google Generative Language REST API via httpx."""

from __future__ import annotations

import time
from typing import Optional

import httpx

from app.ai.exceptions import AIProviderError, AIProviderUnavailable
from app.ai.providers.base import AICompletionResult, AIProvider
from app.ai.schemas import CompletionMeta


class GeminiProvider(AIProvider):
    name = "gemini"
    default_model = "gemini-2.0-flash"
    BASE = "https://generativelanguage.googleapis.com/v1beta"

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
            raise AIProviderUnavailable(self.name, "GEMINI_API_KEY not configured")
        if stream:
            raise NotImplementedError("Gemini streaming not enabled yet")

        model = self.model
        url = f"{self.BASE}/models/{model}:generateContent"
        generation: dict = {
            "temperature": temperature if temperature is not None else self.temperature,
            "maxOutputTokens": max_tokens or self.max_tokens,
        }
        if json_mode:
            generation["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation,
        }
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    url,
                    params={"key": self.api_key},
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            if resp.status_code >= 400:
                raise AIProviderError(
                    self.name,
                    f"HTTP {resp.status_code}: {resp.text[:400]}",
                )
            data = resp.json()
        except AIProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(self.name, str(exc), cause=exc) from exc

        text = ""
        try:
            candidates = data.get("candidates") or []
            parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
            text = "".join(p.get("text") or "" for p in parts)
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(self.name, f"Malformed response: {exc}", cause=exc) from exc

        usage = data.get("usageMetadata") or {}
        latency = (time.perf_counter() - started) * 1000
        return AICompletionResult(
            text,
            meta=CompletionMeta(
                provider=self.name,
                model=self.model,
                latency_ms=round(latency, 1),
                prompt_tokens=usage.get("promptTokenCount"),
                completion_tokens=usage.get("candidatesTokenCount"),
                total_tokens=usage.get("totalTokenCount"),
            ),
            raw=data,
        )
