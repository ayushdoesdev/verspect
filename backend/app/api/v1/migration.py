"""REST API — Universal Migration Intelligence Engine knowledge base & reports."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps.auth import CurrentUser, DbSession
from app.core.database import SyncSessionLocal
from app.models.dependency import Dependency
from app.models.knowledge import (
    DocumentationSource,
    KnowledgeBaseEntry,
    KnowledgeReleaseNote,
    MigrationEngineReport,
    MigrationRule,
    PatchSuggestion,
)
from app.models.repository import Repository
from app.schemas.migration_engine import (
    KnowledgeBaseEntryResponse,
    KnowledgeLookupResponse,
    LearnRulesRequest,
    LearnRulesResponse,
    MigrationEngineReportResponse,
    MigrationRuleResponse,
    PatchSuggestionResponse,
)
from app.scanners.normalize import normalize_package_name

router = APIRouter()


@router.get("/rules", response_model=list[MigrationRuleResponse])
async def list_migration_rules(
    current_user: CurrentUser,
    db: DbSession,
    package_name: Optional[str] = Query(default=None),
    from_version: Optional[str] = Query(default=None),
    to_version: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MigrationRuleResponse]:
    """List stored universal migration rules (knowledge base)."""
    q = select(MigrationRule)
    if package_name:
        q = q.where(MigrationRule.normalized_name == normalize_package_name(package_name))
    if from_version:
        q = q.where(MigrationRule.from_version == from_version)
    if to_version:
        q = q.where(MigrationRule.to_version == to_version)
    if kind:
        q = q.where(MigrationRule.kind == kind)
    q = q.order_by(MigrationRule.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [MigrationRuleResponse.model_validate(r) for r in rows]


@router.get("/knowledge-base", response_model=list[KnowledgeBaseEntryResponse])
async def list_knowledge_base(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[KnowledgeBaseEntryResponse]:
    rows = (
        await db.execute(
            select(KnowledgeBaseEntry)
            .order_by(KnowledgeBaseEntry.last_learned_at.desc().nullslast())
            .limit(limit)
        )
    ).scalars().all()
    return [KnowledgeBaseEntryResponse.model_validate(r) for r in rows]


@router.get("/knowledge-base/{package_name}", response_model=KnowledgeLookupResponse)
async def lookup_knowledge_base(
    package_name: str,
    current_user: CurrentUser,
    db: DbSession,
    from_version: Optional[str] = Query(default=None),
    to_version: Optional[str] = Query(default=None),
) -> KnowledgeLookupResponse:
    """Lookup learned rules, docs, and release notes for any package."""
    normalized = normalize_package_name(package_name)
    entry = (
        await db.execute(
            select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.normalized_name == normalized)
        )
    ).scalar_one_or_none()

    rules_q = select(MigrationRule).where(MigrationRule.normalized_name == normalized)
    if from_version:
        rules_q = rules_q.where(MigrationRule.from_version == from_version)
    if to_version:
        rules_q = rules_q.where(MigrationRule.to_version == to_version)
    rules_q = rules_q.order_by(MigrationRule.created_at.desc()).limit(200)
    rules = (await db.execute(rules_q)).scalars().all()

    release_count = (
        await db.execute(
            select(func.count())
            .select_from(KnowledgeReleaseNote)
            .where(KnowledgeReleaseNote.normalized_name == normalized)
        )
    ).scalar_one()

    docs: list[dict] = []
    if entry:
        sources = (
            await db.execute(
                select(DocumentationSource).where(
                    DocumentationSource.knowledge_base_id == entry.id
                )
            )
        ).scalars().all()
        docs = [
            {
                "source_type": s.source_type,
                "url": s.url,
                "title": s.title,
                "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
                "http_status": s.http_status,
            }
            for s in sources
        ]

    return KnowledgeLookupResponse(
        entry=KnowledgeBaseEntryResponse.model_validate(entry) if entry else None,
        rules=[MigrationRuleResponse.model_validate(r) for r in rules],
        release_notes_count=int(release_count or 0),
        documentation_sources=docs,
    )


@router.get("/reports/{report_id}", response_model=MigrationEngineReportResponse)
async def get_migration_report(
    report_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> MigrationEngineReportResponse:
    report = (
        await db.execute(
            select(MigrationEngineReport).where(MigrationEngineReport.id == report_id)
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    await _assert_report_access(db, current_user, report)
    return MigrationEngineReportResponse.model_validate(report)


@router.get(
    "/reports/{report_id}/patches",
    response_model=list[PatchSuggestionResponse],
)
async def list_report_patches(
    report_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[PatchSuggestionResponse]:
    report = (
        await db.execute(
            select(MigrationEngineReport).where(MigrationEngineReport.id == report_id)
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    await _assert_report_access(db, current_user, report)
    patches = (
        await db.execute(
            select(PatchSuggestion)
            .where(PatchSuggestion.report_id == report_id)
            .order_by(PatchSuggestion.file_path, PatchSuggestion.line)
        )
    ).scalars().all()
    return [PatchSuggestionResponse.model_validate(p) for p in patches]


@router.get(
    "/dependencies/{dependency_id}/report",
    response_model=MigrationEngineReportResponse,
)
async def latest_dependency_report(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    from_version: Optional[str] = Query(default=None),
    to_version: Optional[str] = Query(default=None),
) -> MigrationEngineReportResponse:
    await _assert_dependency_access(db, current_user, dependency_id)
    q = select(MigrationEngineReport).where(
        MigrationEngineReport.dependency_id == dependency_id
    )
    if from_version:
        q = q.where(MigrationEngineReport.from_version == from_version)
    if to_version:
        q = q.where(MigrationEngineReport.to_version == to_version)
    q = q.order_by(MigrationEngineReport.created_at.desc())
    report = (await db.execute(q)).scalars().first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No migration report")
    return MigrationEngineReportResponse.model_validate(report)


@router.post("/learn", response_model=LearnRulesResponse, status_code=status.HTTP_202_ACCEPTED)
async def learn_rules(
    body: LearnRulesRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> LearnRulesResponse:
    """
    Queue background learning for a package version range.
    Rules are stored permanently and reused across repositories.
    AI-assisted extraction requires an AI-entitled plan.
    """
    from app.services.entitlements import require_ai_feature
    from app.services.organizations import get_active_organization
    from app.services.tasks.migration_engine_tasks import learn_library_rules

    org = await get_active_organization(db, current_user)
    await require_ai_feature(db, org=org)

    task = learn_library_rules.delay(
        body.package_name,
        body.from_version,
        body.to_version,
        body.github_url,
        body.force_refresh,
        True,  # allow_ai — gated above
    )
    return LearnRulesResponse(
        status="queued",
        package_name=body.package_name,
        from_version=body.from_version,
        to_version=body.to_version,
        task_id=task.id,
        message="Learning queued — rules will be stored in the knowledge base.",
    )


@router.post(
    "/learn/sync",
    response_model=LearnRulesResponse,
    status_code=status.HTTP_200_OK,
)
async def learn_rules_sync(
    body: LearnRulesRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> LearnRulesResponse:
    """Synchronously learn/reuse rules (for tooling / tests). Requires AI entitlement."""
    from app.ai.analyzer import AIAnalyzer
    from app.migration_engine.engine import MigrationEngine
    from app.services.entitlements import require_ai_feature
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, current_user)
    await require_ai_feature(db, org=org)

    session = SyncSessionLocal()
    try:
        engine = MigrationEngine(session, ai=AIAnalyzer())
        rules = engine.ensure_rules(
            body.package_name,
            body.from_version,
            body.to_version,
            github_url=body.github_url,
            force_refresh=body.force_refresh,
        )
        session.commit()
        return LearnRulesResponse(
            status="completed",
            package_name=body.package_name,
            from_version=body.from_version,
            to_version=body.to_version,
            rules_count=len(rules),
            message=f"Stored/reused {len(rules)} migration rules.",
        )
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    finally:
        session.close()


async def _assert_dependency_access(db: DbSession, user, dependency_id: UUID) -> Dependency:
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, user)
    result = await db.execute(
        select(Dependency)
        .join(Repository, Repository.id == Dependency.repository_id)
        .where(
            Dependency.id == dependency_id,
            Repository.organization_id == org.id,
            Repository.deleted_at.is_(None),
        )
    )
    dep = result.scalar_one_or_none()
    if dep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
    return dep


async def _assert_report_access(
    db: DbSession,
    user,
    report: MigrationEngineReport,
) -> None:
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, user)
    result = await db.execute(
        select(Repository.id).where(
            Repository.id == report.repository_id,
            Repository.organization_id == org.id,
            Repository.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


class CreatePullRequestBody(BaseModel):
    confirm: bool = False


@router.post("/simulations/{simulation_id}/pull-request")
async def create_migration_pull_request(
    simulation_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    body: CreatePullRequestBody,
) -> dict:
    """Open a GitHub PR from validated patches. Requires confirm=true. Never automatic."""
    from app.models.upgrade_simulation import UpgradeSimulation
    from app.services.entitlements import require_ai_migration_assistant
    from app.services.github import (
        GitHubAPIClient,
        GitHubAuthRequired,
        GitHubPermissionDenied,
        GitHubRateLimited,
        github_auth_service,
    )
    from app.services.migration_publish import publish_migration_pull_request
    from app.services.organizations import get_active_organization
    from app.services.repo_access import get_org_repository

    org = await get_active_organization(db, current_user)
    await require_ai_migration_assistant(db, org=org)

    sim = await db.get(UpgradeSimulation, simulation_id)
    if sim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    await get_org_repository(db, current_user, sim.repository_id, write=True)
    dep = await db.get(Dependency, sim.dependency_id)
    repo = await db.get(Repository, sim.repository_id)
    if dep is None or repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    try:
        token = github_auth_service.get_user_github_token(current_user)
        client = GitHubAPIClient(token)
        result = await publish_migration_pull_request(
            db,
            simulation=sim,
            repository=repo,
            dependency=dep,
            github=client,
            confirm=body.confirm,
            actor_login=current_user.github_login,
        )
        await db.commit()
        return result
    except GitHubAuthRequired as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reconnect GitHub") from exc
    except GitHubRateLimited as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except GitHubPermissionDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
