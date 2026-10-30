"""Post-match explainer for Upgrade Simulator summaries.

Deterministic only — never invents replacements or patches.
Team+ LLM patch generation lives in AIMigrationPatchAssistant.
"""

from __future__ import annotations

from typing import Any, Optional

from app.ai.analyzer import AIAnalyzer
from app.migration_engine.models import MatchedUsage, MigrationRuleDTO, ScoringResult


class ImpactExplainer:
    def __init__(self, ai: Optional[AIAnalyzer] = None) -> None:
        # ai retained for call-site compatibility; summaries stay deterministic.
        # Locked plans pass DisabledAIAnalyzer (available=False), never None.
        from app.ai.analyzer import DisabledAIAnalyzer

        self.ai = ai if ai is not None else DisabledAIAnalyzer()

    def explain(
        self,
        *,
        package_name: str,
        from_version: str,
        to_version: str,
        rules: list[MigrationRuleDTO],
        matches: list[MatchedUsage],
        scoring: ScoringResult,
        index_size: int,
        official_references: list[str],
    ) -> dict[str, Any]:
        del index_size, official_references  # reserved for future deterministic context
        return self._deterministic(
            package_name, from_version, to_version, rules, matches, scoring
        )

    def _deterministic(
        self,
        package_name: str,
        from_version: str,
        to_version: str,
        rules: list[MigrationRuleDTO],
        matches: list[MatchedUsage],
        scoring: ScoringResult,
    ) -> dict[str, Any]:
        return {
            "summary": self._default_summary(
                package_name, from_version, to_version, rules, matches, scoring
            ),
            "impact_explanation": (
                f"{len(matches)} semantic usage site(s) matched {len(rules)} stored migration rule(s). "
                "Replacements are taken only from validated rules; unmatched sites require manual review."
            ),
            "effort_rationale": (
                f"Difficulty {scoring.migration_difficulty}; "
                f"~{scoring.migration_time_hours} hours from matched rule effort estimates."
            ),
            "migration_plan": self._default_plan(
                package_name, from_version, to_version, matches, scoring
            ),
        }

    @staticmethod
    def _default_summary(
        package_name: str,
        from_version: str,
        to_version: str,
        rules: list[MigrationRuleDTO],
        matches: list[MatchedUsage],
        scoring: ScoringResult,
    ) -> str:
        if not rules:
            return (
                f"Upgrade {package_name} {from_version} → {to_version}: "
                "no structured migration rules in the knowledge base yet (Unknown). "
                "Manual review required against release notes."
            )
        if not matches:
            return (
                f"Upgrade {package_name} {from_version} → {to_version}: "
                f"{len(rules)} rule(s) available but none matched the semantic AST index. "
                "No automatic patches. Manual review if package-level behavior changed."
            )
        return (
            f"Deterministic migration analysis for {package_name} {from_version} → {to_version}: "
            f"{len(matches)} matched usage(s) across the semantic AST index, "
            f"readiness {scoring.readiness_score:.0f}/100, risk {scoring.risk_score:.0f}/100."
        )

    @staticmethod
    def _default_plan(
        package_name: str,
        from_version: str,
        to_version: str,
        matches: list[MatchedUsage],
        scoring: ScoringResult,
    ) -> list[dict[str, Any]]:
        auto = sum(1 for m in matches if m.rule.auto_fixable and m.rule.after)
        manual = len(matches) - auto
        return [
            {
                "phase": 1,
                "title": f"Pin {package_name} toward {to_version}",
                "description": f"Branch and update from {from_version} toward {to_version}.",
                "reasoning": "Establish a reproducible baseline before code changes.",
                "difficulty": "low",
                "estimated_duration_hours": max(0.5, scoring.migration_time_hours * 0.2),
                "tasks": ["Update manifest pin", "Install", "Run unit tests"],
            },
            {
                "phase": 2,
                "title": "Apply rule-based automatic patches",
                "description": f"Apply {auto} deterministic patch(es) from matched rules with replacements.",
                "reasoning": "Only rule.after values are applied — never AI-invented code.",
                "difficulty": "low" if auto else "trivial",
                "estimated_duration_hours": max(0.25, auto * 0.15),
                "tasks": ["Apply validated patches", "Re-run targeted tests"],
            },
            {
                "phase": 3,
                "title": "Manual review for unmatched / incomplete rules",
                "description": f"Review {manual} matched site(s) without a grounded replacement.",
                "reasoning": "Unknown replacements require human judgment and official docs.",
                "difficulty": scoring.migration_difficulty,
                "estimated_duration_hours": max(0.5, scoring.migration_time_hours * 0.55),
                "tasks": [
                    "Open official_reference links",
                    "Update call sites manually",
                    "Confirm behavior",
                ],
            },
            {
                "phase": 4,
                "title": "Verify and land",
                "description": f"Confirm {package_name}@{to_version} with full regression.",
                "reasoning": "Final readiness gate.",
                "difficulty": "medium",
                "estimated_duration_hours": max(0.5, scoring.migration_time_hours * 0.25),
                "tasks": ["Full test suite", "Staging deploy", "Monitor"],
            },
        ]
