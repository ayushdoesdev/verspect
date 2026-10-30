"""Unit tests for provider-agnostic AI layer."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from app.ai.cache import AICache
from app.ai.exceptions import AIProviderError, AIProviderUnavailable
from app.ai.providers.base import AICompletionResult, AIProvider
from app.ai.providers.factory import AIProviderFactory, SUPPORTED_PROVIDERS
from app.ai.schemas import (
    CompletionMeta,
    DependencySummary,
    UpgradeSummary,
)
from app.ai.service import AIService


class StubProvider(AIProvider):
    name = "stub"
    default_model = "stub-model"

    def __init__(
        self,
        *,
        available: bool = True,
        responses: Optional[dict[str, Any]] = None,
        fail: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(api_key="x", model="stub-model", **kwargs)
        self._available = available
        self._responses = responses or {"ok": True}
        self._fail = fail
        self.calls = 0

    def is_available(self) -> bool:
        return self._available

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
        self.calls += 1
        if self._fail:
            raise AIProviderError(self.name, "forced failure")
        import json

        return AICompletionResult(
            json.dumps(self._responses),
            meta=CompletionMeta(provider=self.name, model=self.model, latency_ms=1.0),
        )


class StubProviderB(StubProvider):
    name = "stub-b"


def test_factory_supported_providers():
    assert set(SUPPORTED_PROVIDERS) == {"ollama", "openai", "gemini", "groq", "openrouter"}


def test_factory_creates_ollama(monkeypatch):
    from app.core.config import Settings
    from app.ai.providers.ollama_provider import OllamaProvider

    settings = Settings(
        secret_key="test-secret-key-1234",
        ai_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="qwen3:8b",
    )
    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: True)
    provider = AIProviderFactory.create("ollama", settings=settings)
    assert provider.name == "ollama"
    assert provider.model == "qwen3:8b"
    assert provider.is_available()


def test_canonical_interface_aliases():
    provider = StubProvider(
        responses={
            "summary": "Upgrade recommended",
            "should_update": "Yes",
            "readiness_score": 80,
            "risk_score": 20,
            "confidence": 0.9,
            "benefits": ["security"],
            "risks": [],
            "estimated_effort": "low",
            "recommended_version": "2.0.0",
        }
    )
    result = provider.analyze({"package_name": "x"})
    assert isinstance(result, UpgradeSummary)
    assert result.readiness_score == 80


def test_factory_rejects_unknown(monkeypatch):
    from app.core.config import Settings

    settings = Settings(
        secret_key="test-secret-key-1234",
        ai_provider="nope",
        openai_api_key="",
    )
    with pytest.raises(AIProviderUnavailable):
        AIProviderFactory.create("nope", settings=settings)


def test_factory_creates_openai_when_keyed(monkeypatch):
    from app.core.config import Settings

    settings = Settings(
        secret_key="test-secret-key-1234",
        ai_provider="openai",
        openai_api_key="sk-test",
        openai_model="gpt-test",
    )
    provider = AIProviderFactory.create("openai", settings=settings)
    assert provider.name == "openai"
    assert provider.model == "gpt-test"
    assert provider.is_available()


def test_factory_fallback_chain_order():
    from app.core.config import Settings

    settings = Settings(
        secret_key="test-secret-key-1234",
        ai_provider="gemini",
        ai_fallback_providers="openrouter,groq,openai",
    )
    chain = AIProviderFactory.fallback_chain(settings=settings)
    assert chain[0] == "gemini"
    assert "openrouter" in chain
    assert "groq" in chain
    assert "openai" in chain


def test_ollama_skips_cloud_fallback_by_default():
    from app.core.config import Settings

    settings = Settings(
        secret_key="test-secret-key-1234",
        ai_provider="ollama",
        ai_fallback_providers="openai,gemini",
        ai_enable_cloud_fallback=False,
    )
    assert AIProviderFactory.fallback_chain(settings=settings) == ["ollama"]


def test_ollama_cloud_fallback_when_enabled():
    from app.core.config import Settings

    settings = Settings(
        secret_key="test-secret-key-1234",
        ai_provider="ollama",
        ai_fallback_providers="openai,gemini",
        ai_enable_cloud_fallback=True,
    )
    chain = AIProviderFactory.fallback_chain(settings=settings)
    assert chain[0] == "ollama"
    assert "openai" in chain
    assert "gemini" in chain


def test_dependency_summary_accepts_bool_should_update():
    provider = StubProvider(
        responses={
            "explanation": "pkg is used",
            "should_update": True,
            "security_summary": "none",
            "migration_summary": "easy",
            "breaking_changes_summary": "none",
        }
    )
    result = provider.dependency_summary({"package_name": "pkg"})
    assert isinstance(result, DependencySummary)
    assert isinstance(result.should_update, str)
    assert "update" in result.should_update.lower() or result.should_update


def test_coerce_should_update_helper():
    from app.ai.schemas import coerce_should_update_str

    assert "Yes" in coerce_should_update_str(True)
    assert "No" in coerce_should_update_str(False)
    assert coerce_should_update_str("Yes — bump") == "Yes — bump"


def test_structured_output_validation():
    provider = StubProvider(
        responses={
            "summary": "Upgrade recommended",
            "should_update": "Yes",
            "readiness_score": 80,
            "risk_score": 20,
            "confidence": 0.9,
            "benefits": ["security"],
            "risks": [],
            "estimated_effort": "low",
            "recommended_version": "2.0.0",
        }
    )
    result = provider.generate_upgrade_summary({"package_name": "x"})
    assert isinstance(result, UpgradeSummary)
    assert result.readiness_score == 80
    assert result.confidence == 0.9


def test_dependency_summary_schema():
    provider = StubProvider(
        responses={
            "explanation": "pkg is used",
            "should_update": "maybe",
            "security_summary": "none",
            "migration_summary": "easy",
            "breaking_changes_summary": "none",
        }
    )
    result = provider.dependency_summary({"package_name": "pkg"})
    assert isinstance(result, DependencySummary)
    assert "pkg" in result.explanation or result.explanation


def test_service_fallback_when_primary_fails():
    primary = StubProvider(fail=True, responses={})
    primary.name = "gemini"
    secondary = StubProvider(
        responses={
            "summary": "from fallback",
            "should_update": "Yes",
            "readiness_score": 70,
            "risk_score": 30,
            "confidence": 0.8,
            "benefits": [],
            "risks": [],
            "estimated_effort": "medium",
        }
    )
    secondary.name = "openrouter"

    cache = MagicMock(spec=AICache)
    cache.make_key.return_value = "k"
    cache.get.return_value = None

    service = AIService(cache=cache, providers=[primary, secondary])
    result = service.generate_upgrade_summary({"package": "x"})
    assert result.summary == "from fallback"
    assert primary.calls == 1
    assert secondary.calls == 1


def test_service_graceful_when_all_fail():
    a = StubProvider(fail=True)
    a.name = "a"
    b = StubProvider(fail=True)
    b.name = "b"
    cache = MagicMock(spec=AICache)
    cache.make_key.return_value = "k"
    cache.get.return_value = None
    service = AIService(cache=cache, providers=[a, b])
    result = service.generate_upgrade_summary({"latest_version": "9.0"})
    assert "unavailable" in result.summary.lower() or result.confidence <= 0.3


def test_service_cache_hit():
    provider = StubProvider(
        responses={
            "summary": "cached-should-not-run",
            "should_update": "No",
            "readiness_score": 10,
            "risk_score": 10,
            "confidence": 0.1,
        }
    )
    cache = MagicMock(spec=AICache)
    cache.make_key.return_value = "k"
    cache.get.return_value = {
        "summary": "from cache",
        "should_update": "Yes",
        "readiness_score": 90,
        "risk_score": 10,
        "confidence": 0.95,
        "benefits": [],
        "risks": [],
        "estimated_effort": "low",
    }
    service = AIService(cache=cache, providers=[provider])
    result = service.generate_upgrade_summary({"x": 1})
    assert result.summary == "from cache"
    assert provider.calls == 0
    assert service.last_meta and service.last_meta.cache_hit is True


def test_complete_json_fallback():
    primary = StubProvider(fail=True)
    primary.name = "gemini"
    secondary = StubProvider(responses={"hello": "world"})
    secondary.name = "groq"
    cache = MagicMock(spec=AICache)
    cache.make_key.return_value = "k"
    cache.get.return_value = None
    service = AIService(cache=cache, providers=[primary, secondary])
    data = service.complete_json("sys", "user")
    assert data == {"hello": "world"}


def test_complete_json_timeout_is_not_empty_dict():
    from app.ai.exceptions import AITimeoutError

    class TimeoutProvider(StubProvider):
        name = "ollama"

        def complete(self, **kwargs):
            self.calls += 1
            raise AITimeoutError(self.name, "timed out")

    cache = MagicMock(spec=AICache)
    cache.make_key.return_value = "k"
    cache.get.return_value = None
    service = AIService(cache=cache, providers=[TimeoutProvider()])
    with pytest.raises(AITimeoutError):
        service.complete_json("sys", "user")


def test_complete_json_unavailable_raises():
    from app.ai.exceptions import AIProviderUnavailable

    class DownProvider(StubProvider):
        name = "ollama"

        def complete(self, **kwargs):
            self.calls += 1
            raise AIProviderUnavailable(self.name, "unreachable")

    cache = MagicMock(spec=AICache)
    cache.make_key.return_value = "k"
    cache.get.return_value = None
    service = AIService(cache=cache, providers=[DownProvider()])
    with pytest.raises(AIProviderUnavailable):
        service.complete_json("sys", "user")


def test_classify_ai_failure_distinguishes_causes():
    from app.ai.exceptions import (
        AIProviderUnavailable,
        AIRateLimitError,
        AITimeoutError,
        AIValidationError,
        classify_ai_failure,
    )

    assert classify_ai_failure(AITimeoutError("ollama", "timed out")) == "ai_timeout"
    assert classify_ai_failure(AIProviderUnavailable("ollama", "down")) == "ai_unavailable"
    assert classify_ai_failure(AIValidationError("bad json")) == "malformed_ai_response"
    assert classify_ai_failure(AIRateLimitError("openai", "429")) == "ai_rate_limited"
    assert classify_ai_failure(RuntimeError("boom")) == "ai_completion_failed"


def test_analyzer_compat_delegates():
    from app.ai.analyzer import AIAnalyzer

    provider = StubProvider(
        responses={
            "explanation": "e",
            "should_update": "s",
            "security_summary": "sec",
            "migration_summary": "mig",
            "breaking_changes_summary": "brk",
        }
    )
    cache = MagicMock(spec=AICache)
    cache.make_key.return_value = "k"
    cache.get.return_value = None
    service = AIService(cache=cache, providers=[provider])
    ai = AIAnalyzer(service=service)
    assert ai.available
    out = ai.explain_dependency({"package_name": "requests"})
    assert out["explanation"] == "e"
    assert out["security_summary"] == "sec"


def test_parse_json_strips_fences():
    provider = StubProvider(responses={"a": 1})
    # Directly test parse helper
    data = AIProvider._parse_json('```json\n{"a": 1}\n```')
    assert data == {"a": 1}
