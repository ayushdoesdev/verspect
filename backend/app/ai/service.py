"""AIService — sole entry point for application code.

AIService → AIProviderFactory → selected provider (+ fallbacks).
Business logic never imports OpenAI / Gemini / Groq / OpenRouter SDKs.
"""

from __future__ import annotations

from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.cache import AICache
from app.ai.exceptions import (
    AIError,
    AIProviderError,
    AIProviderUnavailable,
    AIRateLimitError,
    AITimeoutError,
    AIValidationError,
)
from app.ai.providers.base import AIProvider
from app.ai.providers.factory import AIProviderFactory
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
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class AIService:
    """
    Provider-agnostic AI facade used by the rest of the application.

    Switching providers only requires changing AI_PROVIDER (and the matching API key).
    """

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        cache: Optional[AICache] = None,
        providers: Optional[list[AIProvider]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cache = cache if cache is not None else AICache()
        self._providers = providers
        self._last_meta: Optional[CompletionMeta] = None

    @property
    def providers(self) -> list[AIProvider]:
        if self._providers is None:
            self._providers = AIProviderFactory.create_available_chain(settings=self.settings)
        return self._providers

    @property
    def available(self) -> bool:
        return any(p.is_available() for p in self.providers)

    @property
    def model(self) -> str:
        if self.providers:
            return self.providers[0].model
        return self.settings.llm_model or self.settings.openai_model or "unknown"

    @property
    def provider_name(self) -> str:
        if self.providers:
            return self.providers[0].name
        return (self.settings.ai_provider or "none").lower()

    @property
    def last_meta(self) -> Optional[CompletionMeta]:
        return self._last_meta

    # ------------------------------------------------------------------
    # Health / settings (provider-agnostic)
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Probe the active provider. Used by GET /api/ai/health."""
        import time

        configured = (self.settings.ai_provider or "ollama").strip().lower()
        model = self.model
        if not self.providers:
            return {
                "provider": configured,
                "model": self.settings.llm_model
                or self.settings.ollama_model
                or self.settings.openai_model
                or "unknown",
                "available": False,
                "latency_ms": None,
                "status": "unavailable",
                "message": "No AI providers available. Configure Ollama or a cloud API key.",
                "fallbacks": AIProviderFactory.fallback_chain(settings=self.settings),
            }

        active = self.providers[0]
        model = active.model
        started = time.perf_counter()
        try:
            latency = active.ping()
            # ping() may return 0.0 for key-only checks — measure a real round-trip when 0
            if latency <= 0:
                latency = round((time.perf_counter() - started) * 1000, 1)
            return {
                "provider": active.name,
                "model": model,
                "available": True,
                "latency_ms": latency,
                "status": "ok",
                "message": f"{active.name} ready",
                "fallbacks": [p.name for p in self.providers],
            }
        except Exception as exc:  # noqa: BLE001
            # Try remaining providers for status honesty
            for provider in self.providers[1:]:
                try:
                    latency = provider.ping()
                    return {
                        "provider": provider.name,
                        "model": provider.model,
                        "available": True,
                        "latency_ms": latency if latency > 0 else None,
                        "status": "degraded",
                        "message": f"Primary {active.name} failed ({exc}); using {provider.name}",
                        "fallbacks": [p.name for p in self.providers],
                    }
                except Exception:  # noqa: BLE001
                    continue
            return {
                "provider": active.name,
                "model": model,
                "available": False,
                "latency_ms": None,
                "status": "error",
                "message": str(exc),
                "fallbacks": [p.name for p in self.providers],
            }

    def settings_snapshot(self) -> dict[str, Any]:
        snap = AIProviderFactory.describe_settings(settings=self.settings)
        health = self.health()
        snap.update(
            {
                "connection_status": health.get("status"),
                "latency_ms": health.get("latency_ms"),
                "health_message": health.get("message"),
            }
        )
        return snap

    # ------------------------------------------------------------------
    # Canonical feature entrypoints (Upgrade Advisor, Migration, Patch, Chat)
    # ------------------------------------------------------------------

    def analyze(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> UpgradeSummary:
        return self.generate_upgrade_summary(
            context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
        )

    def summarize(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> DependencySummary | RepositorySummary:
        if context.get("package_name"):
            return self.dependency_summary(
                context,
                repository_id=repository_id,
                dependency_id=dependency_id,
                version=version,
            )
        return self.repository_summary(context, repository_id=repository_id)

    def migration_assistant(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> MigrationPlan:
        return self.generate_upgrade_plan(
            context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
        )

    def generate_patch(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> PatchExplanation:
        return self.explain_patch(
            context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
        )

    def chat(
        self,
        *,
        message: str,
        system: str = "",
        history: Optional[list[dict[str, str]]] = None,
        repository_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Repository Chat — freeform reply via the active provider."""
        if not self.providers:
            return {
                "reply": "AI chat is unavailable — configure Ollama or a cloud provider API key.",
                "provider": self.provider_name,
                "model": self.model,
            }
        errors: list[str] = []
        for provider in self.providers:
            try:
                reply = provider.chat(message=message, system=system, history=history)
                self._last_meta = CompletionMeta(
                    provider=provider.name,
                    model=provider.model,
                    cache_hit=False,
                )
                return {
                    "reply": reply,
                    "provider": provider.name,
                    "model": provider.model,
                    "repository_id": repository_id,
                }
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.name}: {exc}")
                logger.warning("ai_chat_failed", provider=provider.name, error=str(exc))
        return {
            "reply": "All AI providers failed for chat.",
            "provider": self.provider_name,
            "model": self.model,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # High-level operations (validated schemas)
    # ------------------------------------------------------------------

    def generate_upgrade_summary(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> UpgradeSummary:
        return self._run_structured(
            "generate_upgrade_summary",
            lambda p: p.generate_upgrade_summary(context),
            UpgradeSummary,
            context=context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
            fallback=self._fallback_upgrade_summary(context),
        )

    def generate_upgrade_plan(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> MigrationPlan:
        return self._run_structured(
            "generate_upgrade_plan",
            lambda p: p.generate_upgrade_plan(context),
            MigrationPlan,
            context=context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
            fallback=self._fallback_migration_plan(context),
        )

    def summarize_release_notes(
        self,
        *,
        package_name: str,
        from_version: str,
        to_version: str,
        release_notes: str,
        used_symbols: list[str],
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
    ) -> ReleaseNotesSummary:
        ctx = {
            "package_name": package_name,
            "from_version": from_version,
            "to_version": to_version,
            "release_notes": release_notes,
            "used_symbols": used_symbols,
        }
        return self._run_structured(
            "summarize_release_notes",
            lambda p: p.summarize_release_notes(
                package_name=package_name,
                from_version=from_version,
                to_version=to_version,
                release_notes=release_notes,
                used_symbols=used_symbols,
            ),
            ReleaseNotesSummary,
            context=ctx,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=f"{from_version}->{to_version}",
            fallback=self._fallback_release(package_name, from_version, to_version, release_notes),
        )

    def explain_patch(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> PatchExplanation:
        return self._run_structured(
            "explain_patch",
            lambda p: p.explain_patch(context),
            PatchExplanation,
            context=context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
            fallback=PatchExplanation(
                explanation="AI patch explanation unavailable — review the suggested change manually.",
                confidence=0.3,
            ),
        )

    def suggest_alternatives(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> AlternativeRecommendation:
        return self._run_structured(
            "suggest_alternatives",
            lambda p: p.suggest_alternatives(context),
            AlternativeRecommendation,
            context=context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
            fallback=AlternativeRecommendation(alternatives=[]),
        )

    def repository_summary(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
    ) -> RepositorySummary:
        return self._run_structured(
            "repository_summary",
            lambda p: p.repository_summary(context),
            RepositorySummary,
            context=context,
            repository_id=repository_id,
            fallback=RepositorySummary(
                summary="AI repository summary unavailable.",
                recommendations=["Configure an AI provider API key to enable summaries."],
            ),
        )

    def dependency_summary(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> DependencySummary:
        return self._run_structured(
            "dependency_summary",
            lambda p: p.dependency_summary(context),
            DependencySummary,
            context=context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
            fallback=self._fallback_dependency(context),
        )

    def migration_summary(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> MigrationSummary:
        return self._run_structured(
            "migration_summary",
            lambda p: p.migration_summary(context),
            MigrationSummary,
            context=context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
            fallback=MigrationSummary(
                summary="Migration summary unavailable without a configured AI provider.",
                impact_explanation="",
                effort_rationale="",
                migration_plan=[],
            ),
        )

    def security_summary(
        self,
        context: dict[str, Any],
        *,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> SecuritySummary:
        return self._run_structured(
            "security_summary",
            lambda p: p.security_summary(context),
            SecuritySummary,
            context=context,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
            fallback=SecuritySummary(
                summary="Security summary unavailable without a configured AI provider.",
                actionable_steps=["Review CVE details manually."],
            ),
        )

    # ------------------------------------------------------------------
    # Low-level JSON (legacy / specialized callers)
    # ------------------------------------------------------------------

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        operation: str = "complete_json",
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Complete and parse JSON with provider fallback + cache."""
        if not self.providers:
            logger.warning("ai_no_providers", operation=operation)
            return {}

        cache_key = None
        if use_cache:
            cache_key = self.cache.make_key(
                provider=self.provider_name,
                model=self.model,
                operation=operation,
                system=system,
                user=user,
                repository_id=repository_id,
                dependency_id=dependency_id,
                version=version,
            )
            cached = self.cache.get(cache_key)
            if isinstance(cached, dict):
                self._last_meta = CompletionMeta(
                    provider=self.provider_name,
                    model=self.model,
                    cache_hit=True,
                )
                return cached

        errors: list[str] = []
        last_exc: Exception | None = None
        for provider in self.providers:
            try:
                data = provider.complete_json(system, user, operation=operation)
                self._last_meta = CompletionMeta(
                    provider=provider.name,
                    model=provider.model,
                    cache_hit=False,
                )
                if cache_key:
                    # Cache under active provider identity
                    key = self.cache.make_key(
                        provider=provider.name,
                        model=provider.model,
                        operation=operation,
                        system=system,
                        user=user,
                        repository_id=repository_id,
                        dependency_id=dependency_id,
                        version=version,
                    )
                    self.cache.set(key, data)
                return data
            except (AIProviderError, AIValidationError, AIError, Exception) as exc:  # noqa: BLE001
                last_exc = exc
                msg = f"{provider.name}: {exc}"
                errors.append(msg)
                logger.warning("ai_provider_failed", provider=provider.name, operation=operation, error=str(exc))
                continue

        logger.error("ai_all_providers_failed", operation=operation, errors=errors)
        from app.ai.exceptions import AIAllProvidersFailed

        if operation.startswith("migration_assistant"):
            raise AIAllProvidersFailed(errors, cause=last_exc)
        if isinstance(last_exc, (AITimeoutError, AIRateLimitError, AIProviderUnavailable, AIValidationError)):
            raise last_exc
        if last_exc is not None:
            raise last_exc
        raise AIAllProvidersFailed(errors)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_structured(
        self,
        operation: str,
        call,
        schema: Type[T],
        *,
        context: dict[str, Any],
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        version: Optional[str] = None,
        fallback: T,
    ) -> T:
        if not self.providers:
            return fallback

        import json

        system = f"operation:{operation}"
        user = json.dumps(context, default=str)[:2000]
        cache_key = self.cache.make_key(
            provider=self.provider_name,
            model=self.model,
            operation=operation,
            system=system,
            user=user,
            repository_id=repository_id,
            dependency_id=dependency_id,
            version=version,
        )
        cached = self.cache.get(cache_key)
        if isinstance(cached, dict):
            try:
                self._last_meta = CompletionMeta(
                    provider=self.provider_name,
                    model=self.model,
                    cache_hit=True,
                )
                return schema.model_validate(cached)
            except ValidationError:
                pass

        errors: list[str] = []
        for provider in self.providers:
            try:
                result = call(provider)
                self._last_meta = CompletionMeta(
                    provider=provider.name,
                    model=provider.model,
                    cache_hit=False,
                )
                self.cache.set(
                    self.cache.make_key(
                        provider=provider.name,
                        model=provider.model,
                        operation=operation,
                        system=system,
                        user=user,
                        repository_id=repository_id,
                        dependency_id=dependency_id,
                        version=version,
                    ),
                    result.model_dump(),
                )
                return result
            except (AIProviderError, AIValidationError, Exception) as exc:  # noqa: BLE001
                errors.append(f"{provider.name}: {exc}")
                logger.warning("ai_provider_failed", provider=provider.name, operation=operation, error=str(exc))
                continue

        logger.error("ai_all_providers_failed", operation=operation, errors=errors)
        return fallback

    @staticmethod
    def _fallback_dependency(context: dict[str, Any]) -> DependencySummary:
        name = context.get("package_name", "this package")
        current = context.get("current_version")
        latest = context.get("latest_version")
        outdated = context.get("is_outdated")
        vulns = context.get("vulnerability_count", 0)
        return DependencySummary(
            explanation=(
                f"{name} is a project dependency"
                + (f" currently pinned at {current}." if current else ".")
            ),
            should_update=(
                f"Yes — {latest} is available."
                if outdated
                else "No urgent update required based on version data alone."
            ),
            security_summary=(
                f"{vulns} known vulnerabilities affect the installed version."
                if vulns
                else "No known vulnerabilities reported for the installed version."
            ),
            migration_summary="Configure an AI provider API key for detailed migration guidance.",
            breaking_changes_summary="AI analysis unavailable — no provider configured.",
        )

    @staticmethod
    def _fallback_release(
        package: str,
        from_v: str,
        to_v: str,
        notes: str,
    ) -> ReleaseNotesSummary:
        breaking_keywords = ["breaking", "backward incompatible", "removed", "deprecated"]
        lower = (notes or "").lower()
        has_breaking = any(k in lower for k in breaking_keywords)
        return ReleaseNotesSummary(
            ai_summary=f"Release {package} {from_v} → {to_v}. AI summarization unavailable.",
            breaking_changes=["Possible breaking changes detected in notes"] if has_breaking else [],
            deprecated_apis=[],
            new_features=[],
            bug_fixes=[],
            migration_difficulty="medium" if has_breaking else "low",
            risk_score=60 if has_breaking else 25,
            affected_symbols=[],
            has_breaking_changes=has_breaking,
        )

    @staticmethod
    def _fallback_migration_plan(context: dict[str, Any]) -> MigrationPlan:
        pkg = context.get("package_name", "package")
        return MigrationPlan(
            title=f"Migrate {pkg} {context.get('from_version')} → {context.get('to_version')}",
            summary="Detailed AI migration report requires a configured AI provider.",
            difficulty="medium",
            risk_score=50,
            estimated_effort_hours=None,
            breaking_changes=[],
            api_mappings=[],
            affected_files=context.get("affected_files") or [],
            step_by_step=[
                "Review changelog between versions",
                "Run test suite",
                "Update pin and reinstall",
                "Fix failing call sites",
            ],
            testing_checklist=["Unit tests", "Integration tests", "Smoke test critical paths"],
            rollback_plan="Revert the version pin and redeploy previous artifact.",
            recommendation="Update when test coverage allows.",
            should_update=True,
        )

    @staticmethod
    def _fallback_upgrade_summary(context: dict[str, Any]) -> UpgradeSummary:
        return UpgradeSummary(
            summary="Upgrade advisor unavailable without a configured AI provider.",
            should_update="Review version and vulnerability data manually.",
            readiness_score=50.0,
            risk_score=50.0,
            confidence=0.3,
            benefits=[],
            risks=["AI provider not configured"],
            estimated_effort="medium",
            recommended_version=context.get("latest_version") or context.get("to_version"),
        )
