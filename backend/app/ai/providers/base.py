"""Abstract AI provider — all providers implement the same interface."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.exceptions import AIProviderError, AIValidationError
from app.ai.prompts import PromptTemplates
from app.ai.schemas import (
    AlternativeRecommendation,
    CompletionMeta,
    DependencySummary,
    MigrationPlan,
    MigrationSummary,
    PatchExplanation,
    ReleaseNotesSummary,
    RepositorySummary,
    SecuritySummary,
    UpgradeSummary,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class AICompletionResult:
    """Raw completion result — designed so streaming can be added later."""

    def __init__(
        self,
        text: str,
        *,
        meta: CompletionMeta,
        raw: Any = None,
    ) -> None:
        self.text = text
        self.meta = meta
        self.raw = raw


class AIProvider(ABC):
    """
    Provider-agnostic LLM interface.

    Concrete providers only implement transport (`complete` / `is_available`).
    High-level business methods are shared and identical across providers.

    Canonical feature entrypoints (stable for all providers):
      analyze / summarize / migration_assistant / generate_patch / chat
    """

    name: str = "base"
    default_model: str = "unknown"

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "",
        timeout: float = 60.0,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> None:
        self.api_key = api_key or ""
        self.model = model or self.default_model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

    @abstractmethod
    def is_available(self) -> bool:
        """True when credentials are configured and client can be created."""

    @abstractmethod
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
        """
        Non-streaming completion (default).

        When stream=True, providers MAY return an AICompletionResult whose text
        is the full concatenated stream, or raise NotImplementedError until
        streaming is wired. Callers should prefer stream=False today.

        json_mode=True requests structured JSON when the backend supports it.
        """

    def ping(self) -> float:
        """
        Lightweight connectivity check. Returns latency in milliseconds.
        Default: is_available() only (0.0 ms). Providers may override.
        """
        if not self.is_available():
            raise AIProviderError(self.name, "Provider not available")
        return 0.0

    def stream_complete(
        self,
        *,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Streaming hook for future use — default raises NotImplementedError."""
        raise NotImplementedError(f"{self.name} does not support streaming yet")

    # ------------------------------------------------------------------
    # Canonical feature interface (pluggable — do not change business code)
    # ------------------------------------------------------------------

    def analyze(self, context: dict[str, Any]) -> UpgradeSummary:
        """Upgrade Advisor / upgrade impact analysis."""
        return self.generate_upgrade_summary(context)

    def summarize(self, context: dict[str, Any]) -> DependencySummary | RepositorySummary:
        """Dependency or repository summary."""
        if context.get("package_name"):
            return self.dependency_summary(context)
        return self.repository_summary(context)

    def migration_assistant(self, context: dict[str, Any]) -> MigrationPlan:
        """AI Migration Assistant — code-level upgrade plan."""
        return self.generate_upgrade_plan(context)

    def generate_patch(self, context: dict[str, Any]) -> PatchExplanation:
        """Patch Generator — explain / produce patch guidance."""
        return self.explain_patch(context)

    def chat(
        self,
        *,
        message: str,
        system: str = "",
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """Repository Chat — freeform assistant reply (plain text)."""
        system_prompt = system or (
            "You are Dependency Intelligence, an expert Python dependency and "
            "migration assistant. Be concise and actionable."
        )
        # Fold short history into the user turn for providers without multi-turn APIs.
        parts: list[str] = []
        for turn in history or []:
            role = (turn.get("role") or "user").strip()
            content = (turn.get("content") or "").strip()
            if content:
                parts.append(f"{role}: {content}")
        parts.append(f"user: {message}")
        user = "\n".join(parts)
        result = self.complete(system=system_prompt, user=user, json_mode=False)
        return (result.text or "").strip()

    # ------------------------------------------------------------------
    # Shared high-level interface (identical for every provider)
    # ------------------------------------------------------------------

    def generate_upgrade_summary(self, context: dict[str, Any]) -> UpgradeSummary:
        return self._structured(
            PromptTemplates.upgrade_advisor_system(),
            PromptTemplates.upgrade_advisor_user(context),
            UpgradeSummary,
            operation="generate_upgrade_summary",
        )

    def generate_upgrade_plan(self, context: dict[str, Any]) -> MigrationPlan:
        return self._structured(
            PromptTemplates.migration_plan_system(),
            PromptTemplates.migration_plan_user(context),
            MigrationPlan,
            operation="generate_upgrade_plan",
        )

    def summarize_release_notes(
        self,
        *,
        package_name: str,
        from_version: str,
        to_version: str,
        release_notes: str,
        used_symbols: list[str],
    ) -> ReleaseNotesSummary:
        return self._structured(
            PromptTemplates.release_summary_system(),
            PromptTemplates.release_summary_user(
                package_name=package_name,
                from_version=from_version,
                to_version=to_version,
                release_notes=release_notes,
                used_symbols=used_symbols,
            ),
            ReleaseNotesSummary,
            operation="summarize_release_notes",
        )

    def explain_patch(self, context: dict[str, Any]) -> PatchExplanation:
        return self._structured(
            PromptTemplates.patch_explanation_system(),
            PromptTemplates.patch_explanation_user(context),
            PatchExplanation,
            operation="explain_patch",
        )

    def suggest_alternatives(self, context: dict[str, Any]) -> AlternativeRecommendation:
        return self._structured(
            PromptTemplates.alternative_recommendation_system(),
            PromptTemplates.alternative_recommendation_user(context),
            AlternativeRecommendation,
            operation="suggest_alternatives",
        )

    def repository_summary(self, context: dict[str, Any]) -> RepositorySummary:
        return self._structured(
            PromptTemplates.repository_summary_system(),
            PromptTemplates.repository_summary_user(context),
            RepositorySummary,
            operation="repository_summary",
        )

    def dependency_summary(self, context: dict[str, Any]) -> DependencySummary:
        from app.core.config import get_settings

        summary_tokens = int(getattr(get_settings(), "llm_summary_max_tokens", 512) or 512)
        return self._structured(
            PromptTemplates.dependency_summary_system(),
            PromptTemplates.dependency_summary_user(context),
            DependencySummary,
            operation="dependency_summary",
            max_tokens=summary_tokens,
        )

    def migration_summary(self, context: dict[str, Any]) -> MigrationSummary:
        return self._structured(
            PromptTemplates.migration_summary_system(),
            PromptTemplates.migration_summary_user(context),
            MigrationSummary,
            operation="migration_summary",
        )

    def security_summary(self, context: dict[str, Any]) -> SecuritySummary:
        return self._structured(
            PromptTemplates.security_explanation_system(),
            PromptTemplates.security_explanation_user(context),
            SecuritySummary,
            operation="security_summary",
        )

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        operation: str = "complete_json",
    ) -> dict[str, Any]:
        """Low-level JSON completion used by legacy call sites."""
        result = self.complete(system=system, user=user)
        data = self._parse_json(result.text)
        logger.info(
            "ai_completion",
            provider=self.name,
            model=self.model,
            operation=operation,
            latency_ms=result.meta.latency_ms,
            prompt_tokens=result.meta.prompt_tokens,
            completion_tokens=result.meta.completion_tokens,
            cache_hit=False,
        )
        return data

    def _structured(
        self,
        system: str,
        user: str,
        schema: Type[T],
        *,
        operation: str,
        max_tokens: Optional[int] = None,
    ) -> T:
        started = time.perf_counter()
        # Structured JSON paths disable thinking when the provider supports it.
        try:
            result = self.complete(
                system=system,
                user=user,
                max_tokens=max_tokens,
                json_mode=True,
                think=False,
            )
        except TypeError:
            # Older provider signatures without think=
            result = self.complete(
                system=system,
                user=user,
                max_tokens=max_tokens,
                json_mode=True,
            )
        data = self._parse_json(result.text)
        try:
            validated = schema.model_validate(data)
        except ValidationError as exc:
            raise AIValidationError(str(exc), raw=data) from exc
        latency = (time.perf_counter() - started) * 1000
        logger.info(
            "ai_completion",
            provider=self.name,
            model=self.model,
            operation=operation,
            latency_ms=round(latency, 1),
            prompt_tokens=result.meta.prompt_tokens,
            completion_tokens=result.meta.completion_tokens,
            cache_hit=False,
        )
        return validated

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            return {"data": data}
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(text[start : end + 1])
                if isinstance(data, dict):
                    return data
            raise AIValidationError("Provider did not return valid JSON", raw=raw)
