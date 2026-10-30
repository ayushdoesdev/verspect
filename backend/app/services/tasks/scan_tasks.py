"""Celery tasks — full repository scan pipeline."""

from __future__ import annotations

import hashlib
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, select, update

from app.core.celery_app import celery_app
from app.core.database import SyncSessionLocal
from app.core.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    DependencyStatus,
    LicensePolicyAction,
    RepositorySyncStatus,
    ScanStatus,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import decrypt_token
from app.services.job_health import (
    as_aware,
    close_stage_timings,
    heartbeat_is_due,
    record_stage_timing,
)
from app.models.alert import Alert
from app.models.alternative import AlternativeLibrary
from app.models.cve import CVE
from app.models.dependency import Dependency, DependencyVersion
from app.models.library_usage import LibraryUsage
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User
from app.scanners.alternatives import AlternativeEngine
from app.scanners.ast_parser import ASTParser
from app.scanners.classification import RepositoryClassifier
from app.scanners.analyzers import get_analyzer_for_classification
from app.scanners.go_modules import GoModulesClient
from app.scanners.health import HealthScorer, compute_release_frequency_days
from app.scanners.license import LicenseChecker
from app.scanners.manifest import ManifestScanner
from app.scanners.npm import NpmClient
from app.scanners.normalize import normalize_package_name
from app.scanners.osv import OSVClient, OSVUnavailableError
from app.scanners.pipelines import get_pipeline
from app.scanners.pypi import PyPIClient, fetch_recent_downloads
from app.services.ai_upgrade_advisor import ensure_release_stub
from app.services.clone import clone_or_update_repository

logger = get_logger(__name__)
_settings = get_settings()

# Terminal rows must never be re-claimed after acks_late redelivery / worker loss.
TERMINAL_SCAN_STATUSES = frozenset(
    {
        ScanStatus.COMPLETED.value,
        ScanStatus.FAILED.value,
        ScanStatus.CANCELLED.value,
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _scan_is_terminal(scan: Scan) -> bool:
    return (scan.status or "") in TERMINAL_SCAN_STATUSES


def _try_claim_scan(
    session,
    scan: Scan,
    *,
    owner_task_id: str,
    worker_name: str | None,
    retry_count: int | None = None,
) -> bool:
    """
    Atomically claim a scan for this worker.

    The UPDATE only succeeds when ``cancel_requested`` is still false and the
    row is non-terminal — so a concurrent cancel always wins over pickup.
    Never clears ``cancel_requested``.
    """
    pickup = _utcnow()
    values: dict[str, Any] = {
        "status": ScanStatus.RUNNING.value,
        "current_stage": "queued",
        "progress_percent": max(scan.progress_percent or 0, 2),
        "started_at": scan.started_at or pickup,
        "worker_name": worker_name,
        "celery_task_id": owner_task_id,
        "last_heartbeat_at": pickup,
        # Clear recovery banner once a live worker owns the row again.
        "error_message": None,
        "stage_timings": record_stage_timing(scan.stage_timings, "queued", now=pickup),
    }
    if retry_count is not None:
        values["retry_count"] = int(retry_count)

    result = session.execute(
        update(Scan)
        .where(
            Scan.id == scan.id,
            Scan.cancel_requested.is_(False),
            Scan.status.notin_(tuple(TERMINAL_SCAN_STATUSES)),
        )
        .values(**values)
    )
    session.commit()
    session.refresh(scan)
    return int(result.rowcount or 0) == 1


def _fingerprint(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def _is_scan_cancelled(
    session,
    scan_id: str,
    *,
    owner_task_id: Optional[str] = None,
) -> bool:
    """
    Cooperative cancellation / ownership checkpoint.

    Refresh ONLY the Scan row. Never session.expire_all() — that discards
    unflushed Dependency mutations (latest_version, is_outdated, etc.) during
    the enrichment loop.
    """
    s = session.get(Scan, UUID(scan_id))
    if s is None:
        return True
    # Pull latest cancel/ownership flags from DB without invalidating other ORM state.
    session.refresh(s)

    # Another Celery task now owns this scan row — stop without rewriting state.
    if (
        owner_task_id
        and s.celery_task_id
        and s.celery_task_id != owner_task_id
        and s.status != ScanStatus.CANCELLED.value
    ):
        logger.info(
            "scan_superseded_midflight",
            scan_id=scan_id,
            owner_task_id=owner_task_id,
            current_task_id=s.celery_task_id,
        )
        return True
    if s.cancel_requested and s.status != ScanStatus.CANCELLED.value:
        s.status = ScanStatus.CANCELLED.value
        s.current_stage = "cancelled"
        s.completed_at = _utcnow()
        s.stage_timings = close_stage_timings(s.stage_timings)
        repo = session.get(Repository, s.repository_id)
        if repo:
            from app.services.repository_counters import sync_repository_counters

            repo.sync_status = RepositorySyncStatus.IDLE.value
            # Partial writes may already exist; keep counters aligned with rows.
            sync_repository_counters(session, repo)
        session.commit()
        logger.info("scan_cancelled_midflight", scan_id=scan_id)
        return True
    return s.status == ScanStatus.CANCELLED.value


def _update_scan(session, scan: Scan, **kwargs: Any) -> None:
    """
    Persist scan progress plus a worker heartbeat.

    Every progress write doubles as a liveness signal, so a worker that dies
    mid-stage stops refreshing `last_heartbeat_at` and gets reaped.
    """
    stage = kwargs.get("current_stage")
    for k, v in kwargs.items():
        setattr(scan, k, v)

    now = _utcnow()
    if stage:
        scan.stage_timings = record_stage_timing(scan.stage_timings, stage, now=now)
    if heartbeat_is_due(scan.last_heartbeat_at, now=now) or stage:
        scan.last_heartbeat_at = now
    session.commit()


def _running_scan_for_repository(session, scan: Scan) -> Optional[Scan]:
    """
    Another scan actively working on the same repository, if any.

    Only counts scans with a live heartbeat: an abandoned row must not block new
    scans forever (the reaper will fail it independently).
    """
    from app.api.v1.scans import RUNNING_SCAN_STATUSES

    cutoff = _utcnow() - timedelta(minutes=_settings.stale_scan_timeout_minutes)
    candidates = (
        session.execute(
            select(Scan).where(
                Scan.repository_id == scan.repository_id,
                Scan.id != scan.id,
                Scan.status.in_(RUNNING_SCAN_STATUSES),
            )
        )
        .scalars()
        .all()
    )
    for other in candidates:
        beat = as_aware(other.last_heartbeat_at) or as_aware(other.started_at)
        if beat is not None and beat > cutoff:
            return other
    return None


def _heartbeat(session, scan: Scan, *, force: bool = False) -> None:
    """Lightweight liveness ping for long-running stages."""
    now = _utcnow()
    if force or heartbeat_is_due(scan.last_heartbeat_at, now=now):
        scan.last_heartbeat_at = now
        session.commit()


def _record_enrichment_progress(
    session,
    scan: Scan,
    *,
    package: str,
    index: int,
    total: int,
    phase: str,
    publish: bool = False,
) -> None:
    """
    Persist live enrichment UX fields already known in the scan loop.

    Does not change enrichment work — only surfaces package/index/phase for the UI
    via existing scan polling (extra_metadata + progress_percent).
    """
    meta = dict(scan.extra_metadata or {})
    meta["enrichment"] = {
        "package": package,
        "index": index,
        "total": total,
        "phase": phase,
    }
    scan.extra_metadata = meta

    if total > 0:
        frac = max(0.0, min(1.0, (index - 1) / total))
        stage = (scan.current_stage or "").lower()
        if stage == "knowledge":
            base, span = 88, 7
        elif stage == "vulnerabilities":
            base, span = 78, 9
        else:
            base, span = 68, 9
        pct = base + int(frac * span)
        scan.progress_percent = max(int(scan.progress_percent or 0), min(pct, 95))

    if publish:
        scan.last_heartbeat_at = _utcnow()
        session.commit()


@celery_app.task(
    bind=True,
    name="app.services.tasks.scan_tasks.run_repository_scan",
    max_retries=_settings.job_max_auto_retries,
    soft_time_limit=_settings.scan_soft_time_limit_seconds,
    time_limit=_settings.scan_hard_time_limit_seconds,
)
def run_repository_scan(self, scan_id: str) -> dict[str, Any]:
    session = SyncSessionLocal()
    worker_name = getattr(self.request, "hostname", None)
    try:
        scan = session.get(Scan, UUID(scan_id))
        if scan is None:
            logger.error("scan_not_found", scan_id=scan_id)
            return {"error": "scan_not_found"}

        if _scan_is_terminal(scan):
            logger.info(
                "scan_skipped_terminal",
                scan_id=scan_id,
                status=scan.status,
            )
            return {"scan_id": scan_id, "status": scan.status, "skipped": "terminal"}

        if scan.cancel_requested:
            logger.info("scan_skipped_cancelled", scan_id=scan_id)
            return {"scan_id": scan_id, "status": "cancelled"}

        owner_task_id = self.request.id

        # Refuse to run if another live Celery task already owns this scan row.
        if (
            scan.celery_task_id
            and scan.celery_task_id != owner_task_id
            and scan.status in {
                ScanStatus.RUNNING.value,
                ScanStatus.CLONING.value,
                ScanStatus.CLASSIFYING.value,
                ScanStatus.SCANNING_MANIFESTS.value,
                ScanStatus.PARSING_AST.value,
                ScanStatus.CHECKING_VERSIONS.value,
                ScanStatus.CHECKING_VULNERABILITIES.value,
                ScanStatus.CHECKING_LICENSES.value,
                ScanStatus.SCORING_HEALTH.value,
                ScanStatus.ANALYZING_AI.value,
            }
        ):
            beat = as_aware(scan.last_heartbeat_at) or as_aware(scan.started_at)
            if beat and (_utcnow() - beat).total_seconds() < 120:
                logger.warning(
                    "scan_skipped_already_owned",
                    scan_id=scan_id,
                    owner=scan.celery_task_id,
                    this_task=owner_task_id,
                )
                return {
                    "scan_id": scan_id,
                    "status": "already_owned",
                    "owner": scan.celery_task_id,
                }

        # Defense in depth against duplicates. The API refuses to queue a second
        # scan for a repository, but scheduled rescans, webhooks and retries can
        # still race — and two scans writing the same dependency rows deadlock or
        # violate uniqueness constraints.
        conflict = _running_scan_for_repository(session, scan)
        if conflict is not None:
            logger.warning(
                "scan_skipped_duplicate",
                scan_id=scan_id,
                repository_id=str(scan.repository_id),
                in_flight_scan_id=str(conflict.id),
            )
            now = _utcnow()
            scan.status = ScanStatus.CANCELLED.value
            scan.current_stage = "cancelled"
            scan.completed_at = now
            scan.last_heartbeat_at = now
            scan.error_message = (
                "Superseded — another scan is already running for this repository."
            )
            scan.stage_timings = close_stage_timings(scan.stage_timings, now=now)
            session.commit()
            return {"scan_id": scan_id, "status": "duplicate", "active": str(conflict.id)}

        # Atomic claim: cancel_requested / terminal status always beats pickup.
        claimed = _try_claim_scan(
            session,
            scan,
            owner_task_id=owner_task_id,
            worker_name=worker_name,
            retry_count=int(self.request.retries) if self.request.retries else None,
        )
        if not claimed:
            logger.info(
                "scan_claim_lost",
                scan_id=scan_id,
                status=scan.status,
                cancel_requested=scan.cancel_requested,
            )
            if scan.cancel_requested or scan.status == ScanStatus.CANCELLED.value:
                return {"scan_id": scan_id, "status": "cancelled"}
            if _scan_is_terminal(scan):
                return {"scan_id": scan_id, "status": scan.status, "skipped": "terminal"}
            return {"scan_id": scan_id, "status": "claim_failed"}

        logger.info(
            "scan_picked_up",
            scan_id=scan_id,
            worker=worker_name,
            retries=self.request.retries,
        )

        repo = session.get(Repository, scan.repository_id)
        if repo is None:
            _update_scan(
                session,
                scan,
                status=ScanStatus.FAILED.value,
                error_message="Repository not found",
                completed_at=_utcnow(),
            )
            return {"error": "repository_not_found"}

        owner = session.get(User, repo.owner_id)
        token = None
        if owner and owner.github_access_token_encrypted:
            try:
                token = decrypt_token(owner.github_access_token_encrypted)
            except ValueError:
                token = None

        started = as_aware(scan.started_at) or _utcnow()
        _update_scan(
            session,
            scan,
            status=ScanStatus.CLONING.value,
            started_at=started,
            progress_percent=10,
            current_stage="cloning",
            celery_task_id=self.request.id,
        )
        repo.sync_status = RepositorySyncStatus.SYNCING.value
        session.commit()

        # --- Clone ---
        try:
            local_path, sha = clone_or_update_repository(
                str(repo.id),
                repo.clone_url,
                scan.branch or repo.default_branch,
                token=token,
            )
        except Exception as exc:
            _fail_scan(session, scan, repo, f"Clone failed: {exc}")
            raise

        if _is_scan_cancelled(session, scan_id, owner_task_id=owner_task_id):
            return {"scan_id": scan_id, "status": "cancelled"}

        repo.local_path = str(local_path)
        repo.last_commit_sha = sha
        scan.commit_sha = sha
        session.commit()

        # --- Classification (language / package manager / framework) ---
        _update_scan(
            session,
            scan,
            status=ScanStatus.CLASSIFYING.value,
            progress_percent=18,
            current_stage="classifying",
        )
        classification = RepositoryClassifier(local_path).classify()
        pipeline = get_pipeline(classification)
        _apply_classification(repo, classification)
        scan.extra_metadata = {
            **(scan.extra_metadata or {}),
            "classification": classification.to_dict(),
            "pipeline": pipeline.describe(),
        }
        session.commit()

        if not pipeline.can_analyze:
            return _complete_unsupported_scan(
                session,
                scan=scan,
                repo=repo,
                classification=classification,
                pipeline=pipeline,
                started=started,
            )

        # --- Implemented language pipeline stages ---
        _update_scan(
            session,
            scan,
            status=ScanStatus.SCANNING_MANIFESTS.value,
            progress_percent=20,
            current_stage="files",
        )

        # --- Manifests (via LanguageAnalyzer when available) ---
        _update_scan(
            session,
            scan,
            status=ScanStatus.SCANNING_MANIFESTS.value,
            progress_percent=32,
            current_stage="manifests",
        )
        analyzer = get_analyzer_for_classification(classification)
        if analyzer is not None:
            manifest_result = analyzer.parse_dependencies(local_path)
        else:
            manifest_result = ManifestScanner(local_path).scan()
        merged_deps = manifest_result.merged_by_name()
        scan.manifest_files = manifest_result.files_found
        session.commit()

        # Clear previous usages; upsert dependencies
        session.execute(delete(LibraryUsage).where(LibraryUsage.repository_id == repo.id))
        session.commit()

        dep_by_norm: dict[str, Dependency] = {}
        existing = (
            session.execute(select(Dependency).where(Dependency.repository_id == repo.id))
            .scalars()
            .all()
        )
        for d in existing:
            dep_by_norm[d.normalized_name] = d

        seen_norms: set[str] = set()
        for parsed in merged_deps:
            seen_norms.add(parsed.normalized_name)
            dep = dep_by_norm.get(parsed.normalized_name)
            if dep is None:
                dep = Dependency(
                    repository_id=repo.id,
                    package_name=parsed.package_name,
                    normalized_name=parsed.normalized_name,
                    ecosystem=parsed.ecosystem,
                )
                session.add(dep)
                session.flush()
                dep_by_norm[parsed.normalized_name] = dep
            dep.package_name = parsed.package_name
            dep.manifest_source = parsed.manifest_source
            dep.is_direct = parsed.is_direct
            dep.is_dev = parsed.is_dev
            if parsed.version:
                dep.current_version = parsed.version
            dep.version_constraint = parsed.constraint

        # Remove deps no longer in manifests (only if we found manifests)
        if merged_deps:
            for norm, dep in list(dep_by_norm.items()):
                if norm not in seen_norms:
                    session.delete(dep)
                    dep_by_norm.pop(norm, None)
        session.commit()

        known_packages = set(dep_by_norm.keys())

        _update_scan(
            session,
            scan,
            status=ScanStatus.PARSING_AST.value,
            progress_percent=45,
            current_stage="graph",
            dependencies_found=len(dep_by_norm),
        )

        # --- AST / API usage (via LanguageAnalyzer when available) ---
        _update_scan(
            session,
            scan,
            status=ScanStatus.PARSING_AST.value,
            progress_percent=55,
            current_stage="ast",
            dependencies_found=len(dep_by_norm),
        )
        if analyzer is not None:
            ast_result = analyzer.analyze_api_usage(
                local_path, known_packages=list(known_packages)
            )
            dep_graph = analyzer.build_dependency_graph(
                local_path, known_packages=list(known_packages)
            )
            scan.extra_metadata = {
                **(scan.extra_metadata or {}),
                "dependency_graph": dep_graph.to_dict(),
            }
            session.commit()
            try:
                from app.services.dependency_graph_store import persist_dependency_graph

                persist_dependency_graph(
                    session,
                    repository_id=repo.id,
                    graph=dep_graph,
                    dep_by_norm=dep_by_norm,
                )
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("dependency_graph_persist_failed", repository_id=str(repo.id))
        else:
            ast_result = ASTParser(local_path, known_packages=known_packages).scan()
        usage_counts: dict[str, int] = {}
        file_sets: dict[str, set[str]] = {}
        for usage in ast_result.usages:
            ecosystem = analyzer.ecosystem.lower() if analyzer is not None else ""
            if ecosystem in {"npm", "packagist", "rubygems", "crates.io"}:
                norm = usage.package_name.strip().lower()
            elif ecosystem == "go":
                norm = usage.package_name.strip()
            else:
                norm = normalize_package_name(usage.package_name)
            dep = dep_by_norm.get(norm)
            if dep is None:
                continue
            session.add(
                LibraryUsage(
                    dependency_id=dep.id,
                    repository_id=repo.id,
                    package_name=usage.package_name,
                    module_path=usage.module_path,
                    symbol=usage.symbol,
                    fully_qualified_name=usage.fully_qualified_name,
                    usage_kind=usage.usage_kind,
                    file_path=usage.file_path,
                    line=usage.line,
                    column=usage.column,
                    end_line=usage.end_line,
                    end_column=usage.end_column,
                    enclosing_function=usage.enclosing_function,
                    enclosing_class=usage.enclosing_class,
                    code_snippet=usage.code_snippet,
                    alias=usage.alias,
                    extra_metadata={
                        "keyword_args": getattr(usage, "keyword_args", None) or [],
                        **(getattr(usage, "context", None) or {}),
                    },
                )
            )
            usage_counts[norm] = usage_counts.get(norm, 0) + 1
            file_sets.setdefault(norm, set()).add(usage.file_path)
        session.commit()

        for norm, dep in dep_by_norm.items():
            dep.usage_count = usage_counts.get(norm, 0)
            dep.file_count = len(file_sets.get(norm, set()))
        session.commit()

        if _is_scan_cancelled(session, scan_id, owner_task_id=owner_task_id):
            return {"scan_id": scan_id, "status": "cancelled"}

        # --- Versions / licenses / vulns / health ---
        _update_scan(
            session,
            scan,
            status=ScanStatus.CHECKING_VERSIONS.value,
            progress_percent=68,
            current_stage="versions",
            files_parsed=ast_result.files_parsed,
            usages_found=len(ast_result.usages),
        )

        pypi = PyPIClient()
        npm = NpmClient()
        go_modules = GoModulesClient()
        from app.scanners.registries import (
            CratesIoClient,
            MavenCentralClient,
            PackagistClient,
            RubyGemsClient,
        )

        crates = CratesIoClient()
        packagist = PackagistClient()
        rubygems = RubyGemsClient()
        maven_central = MavenCentralClient()
        osv = OSVClient()
        license_checker = LicenseChecker()
        health_scorer = HealthScorer()
        alt_engine = AlternativeEngine()

        # Org license policy (falls back to global env defaults)
        license_reject: list[str] | None = None
        license_warn: list[str] | None = None
        try:
            from app.models.organization import Organization
            from app.services.license_policy import resolve_license_policy_lists

            if repo.organization_id:
                org = session.get(Organization, repo.organization_id)
                if org is not None:
                    license_reject, license_warn = resolve_license_policy_lists(
                        org.settings if isinstance(org.settings, dict) else None
                    )
        except Exception as lic_exc:  # noqa: BLE001
            logger.warning(
                "org_license_policy_resolve_failed",
                scan_id=scan_id,
                error=str(lic_exc)[:300],
            )

        outdated_count = 0
        vuln_total = 0
        osv_unavailable = 0
        license_issues = 0
        alerts_created = 0
        health_scores: list[float] = []
        stage_flags = {"vulnerabilities": False, "knowledge": False}
        maven_licenses = (
            analyzer.pom_licenses(local_path)
            if analyzer is not None
            and analyzer.ecosystem.lower() == "maven"
            and hasattr(analyzer, "pom_licenses")
            else {}
        )

        total_deps = len(dep_by_norm)
        for dep_index, (norm, dep) in enumerate(list(dep_by_norm.items()), start=1):
            # Per-dependency liveness: the enrichment loop is the longest phase and
            # must keep proving the worker is alive so the reaper leaves it alone.
            _record_enrichment_progress(
                session,
                scan,
                package=dep.package_name,
                index=dep_index,
                total=total_deps,
                phase="versions",
                publish=True,
            )
            if dep_index % 10 == 0:
                logger.info(
                    "scan_enrichment_progress",
                    scan_id=scan_id,
                    processed=dep_index,
                    total=total_deps,
                )
            try:
                dep_ecosystem = (dep.ecosystem or "").lower()
                if dep_ecosystem == "maven":
                    info = maven_central.extract_version_info(
                        dep.package_name, dep.current_version
                    )
                    if maven_licenses.get(dep.normalized_name) and not info.get("license_raw"):
                        info["license_raw"] = maven_licenses.get(dep.normalized_name)
                elif dep_ecosystem == "crates.io":
                    info = crates.extract_version_info(
                        dep.package_name, dep.current_version
                    )
                elif dep_ecosystem == "packagist":
                    info = packagist.extract_version_info(
                        dep.package_name, dep.current_version
                    )
                elif dep_ecosystem == "rubygems":
                    info = rubygems.extract_version_info(
                        dep.package_name, dep.current_version
                    )
                elif dep_ecosystem == "npm":
                    info = npm.extract_version_info(
                        dep.package_name, dep.current_version
                    )
                elif dep_ecosystem == "go":
                    info = go_modules.extract_version_info(
                        dep.package_name, dep.current_version
                    )
                else:
                    info = pypi.extract_version_info(
                        dep.package_name, dep.current_version
                    )
            except Exception as exc:
                logger.warning(
                    "package_registry_failed",
                    package=dep.package_name,
                    ecosystem=dep.ecosystem,
                    error=str(exc),
                )
                info = {
                    "latest_version": dep.latest_version,
                    "is_outdated": bool(dep.is_outdated),
                    "major_behind": int(dep.major_behind or 0),
                    "minor_behind": int(dep.minor_behind or 0),
                    "patch_behind": int(dep.patch_behind or 0),
                    "metadata_status": "registry_unavailable",
                }

            dep.latest_version = info.get("latest_version")
            dep.is_outdated = bool(info.get("is_outdated"))
            dep.major_behind = int(info.get("major_behind") or 0)
            dep.minor_behind = int(info.get("minor_behind") or 0)
            dep.patch_behind = int(info.get("patch_behind") or 0)
            dep.summary = info.get("summary") or dep.summary
            dep.home_page = info.get("home_page")
            dep.pypi_url = info.get("pypi_url")
            dep.author = info.get("author")
            dep.requires_python = info.get("requires_python")
            dep.github_repo_url = info.get("github_repo_url")
            dep.last_release_at = info.get("last_release_at")
            if info.get("metadata_status"):
                metadata = dict(dep.extra_metadata or {})
                metadata["version_metadata_status"] = info["metadata_status"]
                dep.extra_metadata = metadata
            _record_enrichment_progress(
                session,
                scan,
                package=dep.package_name,
                index=dep_index,
                total=total_deps,
                phase="metadata",
            )
            if info.get("download_count_month") is not None:
                dep.download_count_month = info["download_count_month"]
            elif (dep.ecosystem or "").lower() == "pypi":
                dep.download_count_month = fetch_recent_downloads(dep.package_name)
            freq_days = compute_release_frequency_days(info.get("releases") or [])
            if freq_days is not None:
                dep.release_frequency_days = freq_days

            # Self-learning: queue migration rule extraction for new version ranges
            if (
                dep.is_outdated
                and dep.current_version
                and dep.latest_version
                and dep.current_version != dep.latest_version
            ):
                try:
                    from app.services.tasks.migration_engine_tasks import learn_library_rules

                    learn_library_rules.delay(
                        dep.package_name,
                        dep.current_version,
                        dep.latest_version,
                        dep.github_repo_url,
                        False,
                    )
                except Exception as learn_exc:
                    logger.debug(
                        "migration_learn_enqueue_skipped",
                        package=dep.package_name,
                        error=str(learn_exc),
                    )

            # Versions table
            session.execute(
                delete(DependencyVersion).where(DependencyVersion.dependency_id == dep.id)
            )
            for rel in (info.get("releases") or [])[:30]:
                session.add(
                    DependencyVersion(
                        dependency_id=dep.id,
                        version=rel["version"],
                        is_current=rel["version"] == dep.current_version,
                        is_latest=rel["version"] == dep.latest_version,
                        is_yanked=bool(rel.get("is_yanked")),
                        released_at=rel.get("released_at"),
                        requires_python=rel.get("requires_python"),
                        download_url=rel.get("download_url"),
                        file_size_bytes=rel.get("file_size_bytes"),
                        checksum_sha256=rel.get("checksum_sha256"),
                    )
                )

            # Make version metadata durable before later cancel checkpoints.
            # Flush only — do not commit (preserves existing transaction boundaries).
            session.flush()

            # License
            lic = license_checker.check(
                license_raw=info.get("license_raw"),
                classifier=info.get("license_classifier"),
                reject_override=license_reject,
                warn_override=license_warn,
            )
            dep.license_spdx = lic["license_spdx"]
            dep.license_raw = lic["license_raw"]
            dep.license_policy_action = lic["license_policy_action"]
            if lic["license_policy_action"] == LicensePolicyAction.REJECT.value:
                license_issues += 1
                alerts_created += _upsert_alert(
                    session,
                    user_id=repo.owner_id,
                    repository_id=repo.id,
                    dependency_id=dep.id,
                    alert_type=AlertType.LICENSE_VIOLATION.value,
                    severity=AlertSeverity.HIGH.value,
                    title=f"License violation: {dep.package_name} ({dep.license_spdx})",
                    description=(
                        f"{dep.package_name} uses {dep.license_spdx or 'unknown'} which is "
                        f"rejected by your license policy."
                    ),
                    recommendation="Replace this dependency or obtain legal approval.",
                    fingerprint=_fingerprint(
                        "license", str(repo.id), dep.normalized_name, dep.license_spdx or ""
                    ),
                )
            elif lic["license_policy_action"] == LicensePolicyAction.WARN.value:
                alerts_created += _upsert_alert(
                    session,
                    user_id=repo.owner_id,
                    repository_id=repo.id,
                    dependency_id=dep.id,
                    alert_type=AlertType.LICENSE_WARNING.value,
                    severity=AlertSeverity.MEDIUM.value,
                    title=f"License warning: {dep.package_name}",
                    description=f"License {dep.license_spdx or 'unknown'} requires review.",
                    recommendation="Review license compatibility with your product.",
                    fingerprint=_fingerprint(
                        "license_warn", str(repo.id), dep.normalized_name, dep.license_spdx or ""
                    ),
                )

            # CVEs
            if not stage_flags["vulnerabilities"]:
                _update_scan(
                    session,
                    scan,
                    status=ScanStatus.CHECKING_VULNERABILITIES.value,
                    progress_percent=78,
                    current_stage="vulnerabilities",
                )
                stage_flags["vulnerabilities"] = True

            if _is_scan_cancelled(session, scan_id, owner_task_id=owner_task_id):
                return {"scan_id": scan_id, "status": "cancelled"}

            _record_enrichment_progress(
                session,
                scan,
                package=dep.package_name,
                index=dep_index,
                total=total_deps,
                phase="vulnerabilities",
                publish=True,
            )
            osv_ok = True
            try:
                vulns = osv.check_dependency(
                    dep.package_name,
                    dep.current_version,
                    ecosystem=dep.ecosystem or "PyPI",
                )
            except OSVUnavailableError:
                osv_ok = False
                osv_unavailable += 1
                vulns = None
                metadata = dict(dep.extra_metadata or {})
                metadata["osv_status"] = "unavailable"
                dep.extra_metadata = metadata

            if osv_ok:
                session.execute(delete(CVE).where(CVE.dependency_id == dep.id))
                critical = 0
                for v in vulns or []:
                    session.add(
                        CVE(
                            dependency_id=dep.id,
                            osv_id=v["osv_id"],
                            cve_id=v.get("cve_id"),
                            aliases=v.get("aliases"),
                            summary=v["summary"],
                            details=v.get("details"),
                            severity=v["severity"],
                            cvss_score=v.get("cvss_score"),
                            cvss_vector=v.get("cvss_vector"),
                            affected_versions=v.get("affected_versions"),
                            fixed_version=v.get("fixed_version"),
                            introduced_version=v.get("introduced_version"),
                            is_fixable=v.get("is_fixable", False),
                            published_at=v.get("published_at"),
                            modified_at=v.get("modified_at"),
                            references=v.get("references"),
                            raw_osv=v.get("raw_osv"),
                            package_name=dep.package_name,
                            ecosystem=v.get("ecosystem") or dep.ecosystem or "PyPI",
                        )
                    )
                    if v["severity"] == AlertSeverity.CRITICAL.value:
                        critical += 1
                        alerts_created += _upsert_alert(
                            session,
                            user_id=repo.owner_id,
                            repository_id=repo.id,
                            dependency_id=dep.id,
                            alert_type=AlertType.CVE.value,
                            severity=AlertSeverity.CRITICAL.value,
                            title=f"Critical vulnerability in {dep.package_name}: {v['osv_id']}",
                            description=v["summary"],
                            recommendation=(
                                f"Upgrade to {v.get('fixed_version')}"
                                if v.get("fixed_version")
                                else "Review advisory and mitigate."
                            ),
                            fingerprint=_fingerprint(
                                "cve", str(repo.id), dep.normalized_name, v["osv_id"]
                            ),
                            source_ref=v["osv_id"],
                        )
                        from app.services.tasks.notification_tasks import notify_alert

                        notify_alert.delay(
                            str(repo.owner_id),
                            {
                                "title": f"Critical CVE in {dep.package_name}",
                                "description": v["summary"],
                                "severity": "critical",
                                "alert_type": "cve",
                                "recommendation": f"Upgrade to {v.get('fixed_version')}",
                            },
                        )

                dep.vulnerability_count = len(vulns or [])
                dep.critical_vuln_count = critical
                dep.has_vulnerabilities = bool(vulns)
                vuln_total += len(vulns or [])
                metadata = dict(dep.extra_metadata or {})
                metadata["osv_status"] = "ok"
                dep.extra_metadata = metadata

            # Status
            if dep.has_vulnerabilities:
                dep.status = DependencyStatus.VULNERABLE.value
            elif dep.license_policy_action == LicensePolicyAction.REJECT.value:
                dep.status = DependencyStatus.LICENSE_ISSUE.value
            elif dep.is_outdated:
                dep.status = DependencyStatus.OUTDATED.value
                outdated_count += 1
                if dep.major_behind > 0:
                    alerts_created += _upsert_alert(
                        session,
                        user_id=repo.owner_id,
                        repository_id=repo.id,
                        dependency_id=dep.id,
                        alert_type=AlertType.MAJOR_RELEASE.value,
                        severity=AlertSeverity.MEDIUM.value,
                        title=f"Major update available: {dep.package_name}",
                        description=(
                            f"{dep.package_name} {dep.current_version} → {dep.latest_version} "
                            f"({dep.major_behind} major version(s) behind)."
                        ),
                        recommendation="Review breaking changes before upgrading.",
                        fingerprint=_fingerprint(
                            "major",
                            str(repo.id),
                            dep.normalized_name,
                            dep.latest_version or "",
                        ),
                    )
            else:
                dep.status = DependencyStatus.UP_TO_DATE.value

            # Health
            _record_enrichment_progress(
                session,
                scan,
                package=dep.package_name,
                index=dep_index,
                total=total_deps,
                phase="health",
            )
            health_metrics: dict[str, Any] = {
                "last_release_at": dep.last_release_at,
                "release_frequency_days": dep.release_frequency_days,
                "github_stars": dep.github_stars,
                "download_count_month": dep.download_count_month,
                "open_issues": dep.open_issues,
                "last_commit_at": dep.last_commit_at,
            }
            if osv_ok:
                health_metrics["vulnerability_count"] = dep.vulnerability_count
                health_metrics["critical_vuln_count"] = dep.critical_vuln_count
            hs = health_scorer.score(health_metrics)
            dep.health_score = hs["health_score"]
            dep.risk_score = health_scorer.risk_score(
                dep.health_score,
                dep.is_outdated,
                dep.major_behind,
                dep.vulnerability_count,
                dep.license_policy_action,
            )
            from app.services.license_policy import license_score_for_action

            components = hs.get("components") or {}
            meta = dict(dep.extra_metadata or {})
            meta["health_components"] = components
            meta["health_weights"] = hs.get("weights") or {}
            meta["health_breakdown"] = {
                "overall": hs["health_score"],
                "security": components.get("security"),
                "maintenance": components.get("maintenance"),
                "freshness": components.get("release_recency"),
                "license": license_score_for_action(dep.license_policy_action),
                "components": components,
                "weights": hs.get("weights") or {},
                "missing_signals": hs.get("missing_signals") or [],
                "completeness": hs.get("completeness"),
                "data_quality": hs.get("data_quality"),
            }
            dep.extra_metadata = meta
            if dep.health_score is not None:
                health_scores.append(dep.health_score)

            # Deterministic release stub (AI summary filled later by AI Upgrade Advisor)
            if dep.is_outdated and dep.current_version and dep.latest_version:
                ensure_release_stub(session, dep)

            # Alternatives (knowledge base — deterministic)
            _record_enrichment_progress(
                session,
                scan,
                package=dep.package_name,
                index=dep_index,
                total=total_deps,
                phase="alternatives",
            )
            session.execute(
                delete(AlternativeLibrary).where(AlternativeLibrary.dependency_id == dep.id)
            )
            if not stage_flags["knowledge"]:
                _update_scan(
                    session,
                    scan,
                    status=ScanStatus.CHECKING_LICENSES.value,
                    progress_percent=88,
                    current_stage="knowledge",
                )
                stage_flags["knowledge"] = True
            alternatives = (
                []
                if (dep.ecosystem or "").lower()
                in {"npm", "go", "maven", "crates.io", "packagist", "rubygems"}
                else alt_engine.suggest(dep.package_name)
            )
            for alt in alternatives:
                session.add(
                    AlternativeLibrary(
                        dependency_id=dep.id,
                        package_name=alt["package_name"],
                        alternative_name=alt["alternative_name"],
                        alternative_normalized=alt["alternative_normalized"],
                        reason=alt["reason"],
                        pros=alt.get("pros"),
                        cons=alt.get("cons"),
                        migration_effort=alt["migration_effort"],
                        api_compatibility=alt.get("api_compatibility"),
                        rank=alt["rank"],
                        confidence=alt.get("confidence"),
                        source=alt.get("source", "knowledge_base"),
                        pypi_url=f"https://pypi.org/project/{alt['alternative_normalized']}/",
                    )
                )

            if _is_scan_cancelled(session, scan_id, owner_task_id=owner_task_id):
                return {"scan_id": scan_id, "status": "cancelled"}

            _record_enrichment_progress(
                session,
                scan,
                package=dep.package_name,
                index=dep_index,
                total=total_deps,
                phase="persisting",
            )
            session.commit()

        # Aggregate repo metrics — Repository Scan finishes here (deterministic).
        meta = dict(scan.extra_metadata or {})
        enrich = dict(meta.get("enrichment") or {})
        enrich["phase"] = "complete"
        if total_deps:
            enrich["index"] = total_deps
            enrich["total"] = total_deps
        meta["enrichment"] = enrich
        if osv_unavailable == 0:
            security_data_status = "ok"
        elif total_deps and osv_unavailable >= total_deps:
            security_data_status = "unavailable"
        else:
            security_data_status = "partial"
        meta["security_data_status"] = security_data_status
        meta["osv_unavailable_count"] = osv_unavailable
        scan.extra_metadata = meta
        _update_scan(
            session,
            scan,
            status=ScanStatus.SCORING_HEALTH.value,
            progress_percent=96,
            current_stage="health",
        )
        avg_health = sum(health_scores) / len(health_scores) if health_scores else None
        repo.dependency_count = len(dep_by_norm)
        repo.outdated_count = outdated_count
        repo.vulnerable_count = sum(1 for d in dep_by_norm.values() if d.has_vulnerabilities)
        repo.license_issues_count = license_issues
        repo.health_score = round(avg_health, 1) if avg_health is not None else None
        repo.critical_alert_count = sum(
            1 for d in dep_by_norm.values() if d.critical_vuln_count > 0
        )
        repo.warning_count = license_issues + outdated_count
        repo.last_synced_at = _utcnow()
        repo.last_scan_id = scan.id
        repo.sync_status = RepositorySyncStatus.IDLE.value

        completed = _utcnow()
        duration = (completed - started).total_seconds()
        scan.stage_timings = close_stage_timings(scan.stage_timings, now=completed)
        _update_scan(
            session,
            scan,
            status=ScanStatus.COMPLETED.value,
            progress_percent=100,
            current_stage="completed",
            completed_at=completed,
            duration_seconds=duration,
            dependencies_found=len(dep_by_norm),
            usages_found=len(ast_result.usages),
            vulnerabilities_found=vuln_total,
            alerts_created=alerts_created,
            files_parsed=ast_result.files_parsed,
            outdated_count=outdated_count,
            license_issues=license_issues,
            summary={
                "manifest_files": manifest_result.files_found,
                "avg_health": avg_health,
                "classification": classification.to_dict(),
                "pipeline": pipeline.describe(),
                "result": "analyzed",
                "security_data_status": security_data_status,
                "osv_unavailable_count": osv_unavailable,
            },
        )
        session.commit()

        # AI Upgrade Advisor — separate job, Pro+ only. Never blocks scan completion.
        ai_advisor_id = None
        try:
            from app.services.tasks.ai_advisor_tasks import enqueue_ai_upgrade_advisor

            advisor = enqueue_ai_upgrade_advisor(
                session,
                repository_id=repo.id,
                parent_scan_id=scan.id,
                triggered_by_user_id=scan.triggered_by_user_id,
            )
            if advisor is not None:
                ai_advisor_id = str(advisor.id)
            session.commit()
        except Exception as ai_exc:  # noqa: BLE001
            session.rollback()
            logger.warning(
                "ai_advisor_enqueue_failed",
                scan_id=scan_id,
                error=str(ai_exc),
            )

        logger.info(
            "scan_completed",
            scan_id=scan_id,
            deps=len(dep_by_norm),
            ai_advisor_scan_id=ai_advisor_id,
        )
        return {
            "scan_id": scan_id,
            "status": "completed",
            "dependencies": len(dep_by_norm),
            "ai_advisor_scan_id": ai_advisor_id,
        }

    except Exception as exc:
        session.rollback()
        logger.exception("scan_failed", scan_id=scan_id, error=str(exc))
        try:
            scan = session.get(Scan, UUID(scan_id))
            repo = session.get(Repository, scan.repository_id) if scan else None
            if scan:
                _fail_scan(session, scan, repo, str(exc), traceback.format_exc())
        except Exception:
            pass
        raise
    finally:
        session.close()


def _apply_classification(repo: Repository, classification) -> None:
    """Persist classifier output on the repository for UI + routing."""
    from app.scanners.language_support import (
        canonicalize_support,
        display_name_for_language,
    )

    status, _label = canonicalize_support(
        language_id=classification.language_id,
        support_status=classification.support_status,
    )
    repo.detected_language = display_name_for_language(
        classification.language_id, fallback=classification.language
    )
    repo.detected_language_id = classification.language_id
    repo.detected_framework = classification.framework
    repo.package_manager = classification.package_manager
    repo.support_status = status or classification.support_status
    repo.classification = classification.to_dict()
    if status:
        repo.classification["support_status"] = status
        repo.classification["support_label"] = _label
        repo.classification["language"] = repo.detected_language
    # Keep GitHub language as fallback display only when classifier is unknown
    if classification.language_id != "unknown" and not repo.language:
        repo.language = classification.language


def _complete_unsupported_scan(
    session,
    *,
    scan: Scan,
    repo: Repository,
    classification,
    pipeline,
    started: datetime,
) -> dict[str, Any]:
    """Finish successfully with a structured Not Yet Supported result (not an error)."""
    from app.scanners.pipelines.base import NotYetSupportedResult

    if hasattr(pipeline, "run_unsupported"):
        outcome = pipeline.run_unsupported(classification)
    else:
        outcome = NotYetSupportedResult(classification=classification)

    # Clear prior Python analysis so unsupported repos don't show stale deps
    session.execute(delete(LibraryUsage).where(LibraryUsage.repository_id == repo.id))
    existing_deps = (
        session.execute(select(Dependency).where(Dependency.repository_id == repo.id))
        .scalars()
        .all()
    )
    for dep in existing_deps:
        session.delete(dep)

    repo.dependency_count = 0
    repo.outdated_count = 0
    repo.vulnerable_count = 0
    repo.critical_alert_count = 0
    repo.warning_count = 0
    repo.license_issues_count = 0
    repo.health_score = None
    repo.last_synced_at = _utcnow()
    repo.last_scan_id = scan.id
    repo.sync_status = RepositorySyncStatus.IDLE.value

    completed = _utcnow()
    duration = (completed - started).total_seconds()
    scan.stage_timings = close_stage_timings(scan.stage_timings, now=completed)
    summary = outcome.to_summary()
    _update_scan(
        session,
        scan,
        status=ScanStatus.COMPLETED.value,
        progress_percent=100,
        current_stage="completed",
        completed_at=completed,
        duration_seconds=duration,
        dependencies_found=0,
        usages_found=0,
        vulnerabilities_found=0,
        alerts_created=0,
        files_parsed=0,
        outdated_count=0,
        license_issues=0,
        error_message=None,
        summary=summary,
    )
    session.commit()
    logger.info(
        "scan_completed_unsupported",
        scan_id=str(scan.id),
        language=classification.language,
        support_status=classification.support_status,
    )
    return {
        "scan_id": str(scan.id),
        "status": "completed",
        "result": "not_yet_supported",
        "language": classification.language,
        "support_status": classification.support_status,
    }


def _fail_scan(
    session,
    scan: Scan,
    repo: Optional[Repository],
    message: str,
    tb: Optional[str] = None,
) -> None:
    now = _utcnow()
    scan.status = ScanStatus.FAILED.value
    scan.error_message = message[:2000]
    scan.error_traceback = (tb or "")[:8000]
    scan.completed_at = now
    scan.current_stage = "failed"
    scan.last_heartbeat_at = now
    scan.stage_timings = close_stage_timings(scan.stage_timings, now=now)
    started = as_aware(scan.started_at)
    if started and scan.duration_seconds is None:
        scan.duration_seconds = (now - started).total_seconds()
    if repo:
        from app.services.repository_counters import sync_repository_counters

        repo.sync_status = RepositorySyncStatus.ERROR.value
        # Keep denormalized counters consistent with any deps written before failure.
        sync_repository_counters(session, repo)
    session.commit()
    logger.error(
        "scan_failed_recorded",
        scan_id=str(scan.id),
        stage=scan.current_stage,
        worker=scan.worker_name,
        retry_count=scan.retry_count,
        reason=message[:200],
    )


def _upsert_alert(
    session,
    *,
    user_id,
    repository_id,
    dependency_id,
    alert_type: str,
    severity: str,
    title: str,
    description: str,
    recommendation: str,
    fingerprint: str,
    source_ref: Optional[str] = None,
) -> int:
    existing = session.execute(
        select(Alert).where(
            Alert.fingerprint == fingerprint,
            Alert.user_id == user_id,
            Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value]),
        )
    ).scalar_one_or_none()
    if existing:
        existing.description = description
        existing.severity = severity
        existing.title = title
        return 0
    session.add(
        Alert(
            user_id=user_id,
            repository_id=repository_id,
            dependency_id=dependency_id,
            alert_type=alert_type,
            severity=severity,
            status=AlertStatus.OPEN.value,
            title=title,
            description=description,
            recommendation=recommendation,
            fingerprint=fingerprint,
            source_ref=source_ref,
        )
    )
    return 1

