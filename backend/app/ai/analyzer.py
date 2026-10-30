""" Backward-compatible AIAnalyzer facade over AIService.

Application code should prefer AIService. AIAnalyzer is preserved so existing
imports and call sites keep working without OpenAI coupling.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from app.ai.schemas import DependencySummary, MigrationPlan, ReleaseNotesSummary
from app.ai.service import AIService
from app.core.logging import get_logger

logger = get_logger(__name__)


class DisabledAIAnalyzer:
    """Non-null stand-in when AI is locked by plan entitlement.

    Always reports ``available=False``. Callers must check ``.available`` before
    invoking LLM methods — never replace this with ``None``.
    """

    @property
    def available(self) -> bool:
        return False

    @property
    def model(self) -> str:
        return "disabled"

    @property
    def service(self) -> AIService:
        raise RuntimeError("AI is disabled by plan entitlement")

    def _respond_json(self, system: str, user: str) -> dict[str, Any]:
        raise RuntimeError(
            "AI is disabled by plan entitlement — callers must check .available first"
        )


class AIAnalyzer:
    """
    Compatibility wrapper.

    Historically this class talked to OpenAI directly. It now delegates to
    AIService so provider switching is controlled solely by AI_PROVIDER.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        *,
        service: Optional[AIService] = None,
    ) -> None:
        # api_key ignored — credentials come from settings / factory
        if api_key:
            logger.debug("ai_analyzer_api_key_arg_ignored")
        self._service = service or AIService()
        self._model_override = model

    @property
    def service(self) -> AIService:
        return self._service

    @property
    def available(self) -> bool:
        return self._service.available

    @property
    def model(self) -> str:
        return self._model_override or self._service.model

    def _respond_json(self, system: str, user: str) -> dict[str, Any]:
        """Legacy low-level JSON helper used by migration/upgrade modules."""
        return self._service.complete_json(system, user, operation="legacy_respond_json")

    def explain_dependency(self, context: dict[str, Any]) -> dict[str, str]:
        summary: DependencySummary = self._service.dependency_summary(
            context,
            dependency_id=str(context.get("dependency_id") or "") or None,
            repository_id=str(context.get("repository_id") or "") or None,
            version=str(context.get("current_version") or "") or None,
        )
        return {
            "explanation": summary.explanation,
            "should_update": summary.should_update,
            "security_summary": summary.security_summary,
            "migration_summary": summary.migration_summary,
            "breaking_changes_summary": summary.breaking_changes_summary,
        }

    def analyze_release_notes(
        self,
        package_name: str,
        from_version: str,
        to_version: str,
        release_notes: str,
        used_symbols: list[str],
    ) -> dict[str, Any]:
        result: ReleaseNotesSummary = self._service.summarize_release_notes(
            package_name=package_name,
            from_version=from_version,
            to_version=to_version,
            release_notes=release_notes,
            used_symbols=used_symbols,
        )
        data = result.model_dump()
        data.setdefault("has_breaking_changes", bool(data.get("breaking_changes")))
        return data

    def generate_migration_report(self, context: dict[str, Any]) -> dict[str, Any]:
        plan: MigrationPlan = self._service.generate_upgrade_plan(
            context,
            dependency_id=str(context.get("dependency_id") or "") or None,
            repository_id=str(context.get("repository_id") or "") or None,
            version=f"{context.get('from_version')}->{context.get('to_version')}",
        )
        return plan.model_dump()

    def suggest_alternatives(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        result = self._service.suggest_alternatives(
            context,
            dependency_id=str(context.get("dependency_id") or "") or None,
            repository_id=str(context.get("repository_id") or "") or None,
        )
        return [a.model_dump() for a in result.alternatives]


AIHandle = Union[AIAnalyzer, DisabledAIAnalyzer]


def resolve_ai_handle(*, enabled: bool) -> AIHandle:
    """Return a live analyzer when enabled, otherwise a locked handle (never None)."""
    if enabled:
        return AIAnalyzer()
    return DisabledAIAnalyzer()
