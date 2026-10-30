"""Ollama provider — local OpenAI-compatible / native chat API via httpx."""

from __future__ import annotations

import time
from typing import Optional

import httpx

from app.ai.exceptions import AIProviderError, AIProviderUnavailable
from app.ai.providers.base import AICompletionResult, AIProvider
from app.ai.schemas import CompletionMeta


class OllamaProvider(AIProvider):
    """Local LLM via Ollama. No cloud API key required."""

    name = "ollama"
    default_model = "qwen3:8b"

    def __init__(self, *, base_url: str = "http://localhost:11434", **kwargs) -> None:
        # Ollama does not use cloud API keys; keep a placeholder so shared code paths work.
        kwargs.setdefault("api_key", "ollama")
        super().__init__(**kwargs)
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")

    def is_available(self) -> bool:
        if not self.base_url:
            return False
        try:
            with httpx.Client(timeout=1.5) as client:
                resp = client.get(f"{self.base_url}/api/tags")
            return resp.status_code < 400
        except Exception:  # noqa: BLE001
            return False

    def ping(self) -> float:
        """Return latency ms to Ollama /api/tags, or raise if unreachable."""
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=min(5.0, self.timeout)) as client:
                resp = client.get(f"{self.base_url}/api/tags")
            if resp.status_code >= 400:
                raise AIProviderError(self.name, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except AIProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AIProviderUnavailable(self.name, f"Ollama unreachable at {self.base_url}: {exc}", cause=exc) from exc
        return round((time.perf_counter() - started) * 1000, 1)

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
        if not self.base_url:
            raise AIProviderUnavailable(self.name, "OLLAMA_BASE_URL not configured")
        # Avoid a second /api/tags round-trip on every completion when the chain
        # already filtered unavailable providers at init.
        if stream:
            raise NotImplementedError("Ollama streaming not enabled yet")

        started = time.perf_counter()
        predict = max_tokens if max_tokens is not None else self.max_tokens
        payload: dict = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_predict": predict,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["format"] = "json"
            # qwen3 and similar "thinking" models waste tokens + latency on reasoning
            # for structured JSON — disable unless explicitly requested.
            payload["think"] = False if think is None else think
        elif think is not None:
            payload["think"] = think

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=payload)
            if resp.status_code == 429:
                from app.ai.exceptions import AIRateLimitError

                raise AIRateLimitError(self.name, "rate limited or quota exceeded")
            if resp.status_code >= 400:
                raise AIProviderError(self.name, f"HTTP {resp.status_code}: {resp.text[:400]}")
            data = resp.json()
            message = data.get("message") or {}
            text = message.get("content") or ""
            # Some builds put JSON only in thinking when think wasn't disabled —
            # prefer content; fall back to thinking if content empty.
            if not text and isinstance(message.get("thinking"), str):
                text = message["thinking"]
        except AIProviderError:
            raise
        except httpx.TimeoutException as exc:
            from app.ai.exceptions import AITimeoutError

            raise AITimeoutError(self.name, "timed out", cause=exc) from exc
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(self.name, str(exc), cause=exc) from exc

        eval_counts = data.get("prompt_eval_count"), data.get("eval_count")
        latency = (time.perf_counter() - started) * 1000
        prompt_tokens = eval_counts[0]
        completion_tokens = eval_counts[1]
        total = None
        if prompt_tokens is not None and completion_tokens is not None:
            total = int(prompt_tokens) + int(completion_tokens)

        return AICompletionResult(
            text,
            meta=CompletionMeta(
                provider=self.name,
                model=self.model,
                latency_ms=round(latency, 1),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
            ),
            raw=data,
        )
