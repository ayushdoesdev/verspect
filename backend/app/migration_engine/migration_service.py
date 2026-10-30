"""High-level migration service — persist engine reports & patches, expose to API/simulator."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.analyzer import AIAnalyzer
from app.core.logging import get_logger
from app.migration_engine.engine import MigrationEngine
from app.migration_engine.models import UpgradeEngineReport
from app.models.knowledge import MigrationEngineReport, MigrationRule, PatchSuggestion
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)


class MigrationService:
    def __init__(
        self,
        session: Session,
        ai: Optional[AIAnalyzer] = None,
        *,
        allow_ai: bool = True,
    ) -> None:
        self.session = session
        self.engine = MigrationEngine(session, ai=ai, allow_ai=allow_ai)

    def run_for_dependency(
        self,
        *,
        dependency_id: UUID,
        repository_id: UUID,
        package_name: str,
        from_version: str,
        to_version: str,
        usages: list[dict[str, Any]],
        github_url: Optional[str] = None,
        cve_hints: Optional[list[str]] = None,
        simulation_id: Optional[UUID] = None,
        force_refresh_rules: bool = False,
    ) -> tuple[MigrationEngineReport, UpgradeEngineReport]:
        report = self.engine.analyze_upgrade(
            package_name=package_name,
            from_version=from_version,
            to_version=to_version,
            usages=usages,
            github_url=github_url,
            cve_hints=cve_hints,
            force_refresh_rules=force_refresh_rules,
        )
        orm = self.persist_report(
            report,
            dependency_id=dependency_id,
            repository_id=repository_id,
            simulation_id=simulation_id,
        )
        return orm, report

    def persist_report(
        self,
        report: UpgradeEngineReport,
        *,
        dependency_id: UUID,
        repository_id: UUID,
        simulation_id: Optional[UUID] = None,
    ) -> MigrationEngineReport:
        orm = MigrationEngineReport(
            dependency_id=dependency_id,
            repository_id=repository_id,
            simulation_id=simulation_id,
            package_name=report.package_name,
            normalized_name=normalize_package_name(report.package_name),
            from_version=report.from_version,
            to_version=report.to_version,
            readiness_score=report.scoring.readiness_score,
            risk_score=report.scoring.risk_score,
            confidence=report.scoring.confidence,
            migration_difficulty=report.scoring.migration_difficulty,
            migration_time_hours=report.scoring.migration_time_hours,
            security_improvement=report.scoring.security_improvement,
            performance_improvement=report.scoring.performance_improvement,
            technical_debt_reduction=report.scoring.technical_debt_reduction,
            affected_files=report.affected_files,
            affected_symbols=report.affected_symbols,
            matched_rule_ids=[r.id for r in report.rules if r.id],
            auto_fix_count=report.scoring.auto_fix_count,
            manual_fix_count=report.scoring.manual_fix_count,
            summary=report.summary,
            official_references=report.official_references,
            scoring_breakdown=report.scoring.breakdown,
            extra_metadata={
                "migration_plan": report.migration_plan,
                "security_improvements": report.security_improvements,
                "performance_improvements": report.performance_improvements,
            },
        )
        self.session.add(orm)
        self.session.flush()

        for patch in report.patches:
            rule_uuid = None
            if patch.rule_id:
                try:
                    rule_uuid = UUID(patch.rule_id)
                except (ValueError, TypeError):
                    rule_uuid = None
            self.session.add(
                PatchSuggestion(
                    report_id=orm.id,
                    rule_id=rule_uuid,
                    file_path=patch.file_path,
                    line=patch.line,
                    symbol=patch.symbol,
                    current_code=patch.current_code,
                    suggested_code=patch.suggested_code,
                    unified_diff=patch.unified_diff,
                    reason=patch.reason,
                    confidence=patch.confidence,
                    official_reference=patch.official_reference,
                    auto_fixable=patch.auto_fixable,
                    validation_status=patch.validation_status,
                    validation_errors=patch.validation_errors,
                )
            )
        self.session.flush()
        logger.info(
            "migration_report_persisted",
            report_id=str(orm.id),
            package=report.package_name,
            patches=len(report.patches),
        )
        return orm

    def list_rules(
        self,
        package_name: Optional[str] = None,
        from_version: Optional[str] = None,
        to_version: Optional[str] = None,
        limit: int = 100,
    ) -> list[MigrationRule]:
        q = select(MigrationRule)
        if package_name:
            q = q.where(
                MigrationRule.normalized_name == normalize_package_name(package_name)
            )
        if from_version:
            q = q.where(MigrationRule.from_version == from_version)
        if to_version:
            q = q.where(MigrationRule.to_version == to_version)
        q = q.order_by(MigrationRule.created_at.desc()).limit(limit)
        return list(self.session.execute(q).scalars().all())

    def get_latest_report(
        self,
        dependency_id: UUID,
        from_version: Optional[str] = None,
        to_version: Optional[str] = None,
    ) -> Optional[MigrationEngineReport]:
        q = select(MigrationEngineReport).where(
            MigrationEngineReport.dependency_id == dependency_id
        )
        if from_version:
            q = q.where(MigrationEngineReport.from_version == from_version)
        if to_version:
            q = q.where(MigrationEngineReport.to_version == to_version)
        q = q.order_by(MigrationEngineReport.created_at.desc())
        return self.session.execute(q).scalars().first()
