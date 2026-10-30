"""Repository import, list, and management endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps.auth import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.enums import RepositorySyncStatus, ScanStatus, ScanType
from app.core.mixins import utcnow
from app.core.pagination import PaginatedResponse, PaginationParams
from app.models.repository import Repository
from app.models.scan import Scan
from app.schemas.repository import (
    GitHubRepoListItem,
    RepositoryImportRequest,
    RepositoryResponse,
    RepositoryUpdateRequest,
)
from app.services.github import (
    GitHubAPIClient,
    GitHubAuthRequired,
    GitHubRateLimited,
    github_auth_service,
)

router = APIRouter()
settings = get_settings()


def _reconnect_github() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Reconnect GitHub",
    )


async def _publish_committed_import_scans(db: DbSession, scan_ids: list[UUID]) -> None:
    """
    Publish Repository Scan tasks only after Scan rows are durable.

    Callers must commit (or otherwise persist) the Scan rows before invoking this.
    Publishing first races the worker against an uncommitted transaction and yields
    scan_not_found on idle workers.
    """
    if not scan_ids:
        return
    from app.services.tasks.scan_tasks import run_repository_scan

    for scan_id in scan_ids:
        scan = await db.get(Scan, scan_id)
        if scan is None:
            continue
        task = run_repository_scan.delay(str(scan.id))
        scan.celery_task_id = task.id
    await db.commit()


@router.get("/github", response_model=list[GitHubRepoListItem])
async def list_github_repositories(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> list[GitHubRepoListItem]:
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, current_user)
    try:
        token = github_auth_service.get_user_github_token(current_user)
        client = GitHubAPIClient(token)
        repos = await client.list_repositories(page=page, per_page=per_page)
    except GitHubAuthRequired as exc:
        raise _reconnect_github() from exc
    except GitHubRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc

    existing = await db.execute(
        select(Repository.github_repo_id).where(
            Repository.organization_id == org.id,
            Repository.deleted_at.is_(None),
        )
    )
    imported_ids = {row[0] for row in existing.all()}

    return [
        GitHubRepoListItem(
            github_repo_id=r["id"],
            full_name=r["full_name"],
            name=r["name"],
            owner_login=r["owner"]["login"],
            description=r.get("description"),
            html_url=r["html_url"],
            language=r.get("language"),
            is_private=r["private"],
            is_fork=r["fork"],
            stars_count=r.get("stargazers_count", 0),
            default_branch=r.get("default_branch", "main"),
            already_imported=r["id"] in imported_ids,
        )
        for r in repos
    ]


@router.post("/import", response_model=list[RepositoryResponse], status_code=status.HTTP_201_CREATED)
async def import_repositories(
    body: RepositoryImportRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> list[RepositoryResponse]:
    from app.services.entitlements import (
        count_scans_this_month,
        require_write_access,
    )
    from app.services.organizations import get_active_organization
    from app.services.plans import assert_repo_limit, assert_scan_limit

    org = await get_active_organization(db, current_user)
    entitlements = await require_write_access(db, org=org, feature="import")
    from app.services.billing.soft_limits import count_active_repositories

    existing_count = await count_active_repositories(
        db, organization_id=org.id
    )
    if not existing_count:
        existing_count = await count_active_repositories(
            db, owner_id=current_user.id
        )
    new_ids = list(body.github_repo_ids or [])
    # Count only not-yet-imported
    already = await db.execute(
        select(Repository.github_repo_id).where(
            Repository.organization_id == org.id,
            Repository.github_repo_id.in_(new_ids),
            Repository.deleted_at.is_(None),
        )
    )
    already_set = {r[0] for r in already.all()}
    adding = len([i for i in new_ids if i not in already_set])
    assert_repo_limit(org.plan, int(existing_count or 0), adding=adding)

    try:
        token = github_auth_service.get_user_github_token(current_user)
        client = GitHubAPIClient(token)
        all_repos = await client.list_repositories(page=1, per_page=100)
        # Fetch additional pages if needed
        page = 2
        while True:
            more = await client.list_repositories(page=page, per_page=100)
            if not more:
                break
            all_repos.extend(more)
            if len(more) < 100:
                break
            page += 1
            if page > 20:
                break
    except GitHubAuthRequired as exc:
        raise _reconnect_github() from exc

    by_id = {r["id"]: r for r in all_repos}
    imported: list[Repository] = []
    # Defer Celery publish until after commit so idle workers cannot race
    # an uncommitted Scan INSERT (scan_not_found → "Waiting for worker").
    pending_scan_ids: list[UUID] = []

    for repo_id in body.github_repo_ids:
        gh = by_id.get(repo_id)
        if gh is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GitHub repository {repo_id} not found or inaccessible",
            )

        existing = await db.execute(
            select(Repository).where(
                Repository.organization_id == org.id,
                Repository.github_repo_id == repo_id,
                Repository.deleted_at.is_(None),
            )
        )
        repo = existing.scalar_one_or_none()
        if repo is None:
            repo = Repository(
                owner_id=current_user.id,
                organization_id=org.id,
                github_repo_id=gh["id"],
                full_name=gh["full_name"],
                name=gh["name"],
                owner_login=gh["owner"]["login"],
                description=gh.get("description"),
                html_url=gh["html_url"],
                clone_url=gh["clone_url"],
                default_branch=gh.get("default_branch", "main"),
                language=gh.get("language"),
                is_private=gh["private"],
                is_fork=gh["fork"],
                stars_count=gh.get("stargazers_count", 0),
                forks_count=gh.get("forks_count", 0),
                open_issues_count=gh.get("open_issues_count", 0),
                topics=gh.get("topics", []),
                sync_status=RepositorySyncStatus.NEVER_SYNCED.value,
            )
            db.add(repo)
            await db.flush()
        elif not repo.organization_id:
            repo.organization_id = org.id

        if body.install_webhooks and entitlements.webhooks:
            webhook_url = f"{settings.api_url}/api/v1/webhooks/github"
            try:
                hook = await client.create_webhook(
                    gh["owner"]["login"],
                    gh["name"],
                    webhook_url,
                    settings.github_webhook_secret,
                )
                repo.webhook_id = hook["id"]
                repo.webhook_active = True
            except Exception:
                repo.webhook_active = False

        if body.trigger_scan:
            scans_used = await count_scans_this_month(
                db, org=org, owner_user_id=current_user.id
            )
            assert_scan_limit(org.plan, scans_used)
            now = utcnow()
            scan = Scan(
                repository_id=repo.id,
                triggered_by_user_id=current_user.id,
                scan_type=ScanType.FULL.value,
                branch=repo.default_branch,
                status=ScanStatus.QUEUED.value,
                progress_percent=0,
                current_stage="queued",
                queued_at=now,
                stage_timings=[],
            )
            db.add(scan)
            await db.flush()
            repo.sync_status = RepositorySyncStatus.SYNCING.value
            pending_scan_ids.append(scan.id)

        imported.append(repo)

    await db.flush()
    # Persist repositories + Scan rows before any worker can see the task.
    if pending_scan_ids:
        await db.commit()
        await _publish_committed_import_scans(db, pending_scan_ids)

    for repo in imported:
        await db.refresh(repo)
    return [RepositoryResponse.model_validate(r) for r in imported]


@router.get("", response_model=PaginatedResponse[RepositoryResponse])
async def list_repositories(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    language: Optional[str] = None,
    is_watching: Optional[bool] = None,
    lifecycle: Optional[str] = Query(
        None,
        pattern="^(all|active|archived)$",
        description="Filter by lifecycle: all | active | archived. Prefers over include_archived/archived_only.",
    ),
    include_archived: bool = Query(
        False,
        description="When true (and lifecycle unset), include both active and archived repositories.",
    ),
    archived_only: bool = Query(
        False,
        description="When true (and lifecycle unset), return only archived repositories.",
    ),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> PaginatedResponse[RepositoryResponse]:
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, current_user)
    query = select(Repository).where(
        Repository.organization_id == org.id,
        Repository.deleted_at.is_(None),
    )
    count_query = select(func.count()).select_from(Repository).where(
        Repository.organization_id == org.id,
        Repository.deleted_at.is_(None),
    )

    # lifecycle takes precedence; default remains active-only for backward compatibility
    effective = lifecycle
    if effective is None:
        if archived_only:
            effective = "archived"
        elif include_archived:
            effective = "all"
        else:
            effective = "active"

    if effective == "archived":
        query = query.where(Repository.is_archived.is_(True))
        count_query = count_query.where(Repository.is_archived.is_(True))
    elif effective == "active":
        query = query.where(Repository.is_archived.is_(False))
        count_query = count_query.where(Repository.is_archived.is_(False))
    # effective == "all" → no archive filter; archived repos remain accessible

    if search:
        pattern = f"%{search}%"
        filt = or_(
            Repository.full_name.ilike(pattern),
            Repository.description.ilike(pattern),
            Repository.name.ilike(pattern),
        )
        query = query.where(filt)
        count_query = count_query.where(filt)
    if language:
        query = query.where(Repository.language == language)
        count_query = count_query.where(Repository.language == language)
    if is_watching is not None:
        query = query.where(Repository.is_watching == is_watching)
        count_query = count_query.where(Repository.is_watching == is_watching)

    sort_col = getattr(Repository, sort_by, Repository.updated_at)
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query)).scalars().all()
    return PaginatedResponse.create(
        items=[RepositoryResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> RepositoryResponse:
    repo = await _get_org_repo(db, current_user, repository_id)
    return RepositoryResponse.model_validate(repo)


@router.get("/{repository_id}/dependency-graph")
async def get_dependency_graph(
    repository_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Return persisted dependency graph nodes and edges for this repository."""
    from app.models.dependency import Dependency
    from app.models.dependency_relationship import DependencyRelationship

    repo = await _get_org_repo(db, current_user, repository_id)
    deps = (
        await db.execute(
            select(Dependency).where(Dependency.repository_id == repo.id)
        )
    ).scalars().all()
    edges = (
        await db.execute(
            select(DependencyRelationship).where(
                DependencyRelationship.repository_id == repo.id
            )
        )
    ).scalars().all()
    nodes = [
        {
            "id": str(d.id),
            "package_name": d.package_name,
            "normalized_name": d.normalized_name,
            "version": d.current_version,
            "is_direct": d.is_direct,
            "is_outdated": d.is_outdated,
            "has_vulnerabilities": d.has_vulnerabilities,
            "health_score": d.health_score,
            "license_spdx": d.license_spdx,
        }
        for d in deps
    ]
    edge_rows = [
        {
            "id": str(e.id),
            "parent_dependency_id": str(e.parent_dependency_id),
            "child_dependency_id": str(e.child_dependency_id),
            "relationship": e.edge_type,
            "source": e.source,
        }
        for e in edges
    ]
    return {
        "repository_id": str(repo.id),
        "nodes": nodes,
        "edges": edge_rows,
        "node_count": len(nodes),
        "edge_count": len(edge_rows),
    }


@router.patch("/{repository_id}", response_model=RepositoryResponse)
async def update_repository(
    repository_id: UUID,
    body: RepositoryUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> RepositoryResponse:
    from app.services.organizations import get_active_organization
    from app.services import repository_lifecycle as lifecycle

    org = await get_active_organization(db, current_user)
    repo = await _get_org_repo(db, current_user, repository_id, write=True)
    data = body.model_dump(exclude_unset=True)

    # Prefer lifecycle helpers when archive / watching flags change
    if "is_archived" in data:
        archived = bool(data.pop("is_archived"))
        try:
            if archived and not repo.is_archived:
                await lifecycle.archive_repository(
                    db, repo, actor=current_user, plan=org.plan
                )
            elif not archived and repo.is_archived:
                await lifecycle.unarchive_repository(
                    db, repo, actor=current_user, plan=org.plan
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "is_watching" in data:
        watching = bool(data.pop("is_watching"))
        try:
            if watching and not repo.is_watching:
                await lifecycle.resume_sync(db, repo, actor=current_user, plan=org.plan)
            elif not watching and repo.is_watching:
                await lifecycle.pause_sync(db, repo, actor=current_user, plan=org.plan)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    for key, value in data.items():
        setattr(repo, key, value)
    await db.commit()
    await db.refresh(repo)
    return RepositoryResponse.model_validate(repo)


@router.post("/{repository_id}/archive", response_model=RepositoryResponse)
async def archive_repository(
    repository_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> RepositoryResponse:
    from app.services.organizations import get_active_organization
    from app.services import repository_lifecycle as lifecycle

    org = await get_active_organization(db, current_user)
    repo = await _get_org_repo(db, current_user, repository_id, write=True)
    if repo.is_archived:
        return RepositoryResponse.model_validate(repo)
    await lifecycle.archive_repository(db, repo, actor=current_user, plan=org.plan)
    await db.commit()
    await db.refresh(repo)
    return RepositoryResponse.model_validate(repo)


@router.post("/{repository_id}/unarchive", response_model=RepositoryResponse)
async def unarchive_repository(
    repository_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> RepositoryResponse:
    from app.services.billing.soft_limits import count_active_repositories
    from app.services.organizations import get_active_organization
    from app.services.plans import assert_repo_limit
    from app.services import repository_lifecycle as lifecycle

    org = await get_active_organization(db, current_user)
    repo = await _get_org_repo(db, current_user, repository_id, write=True)
    if not repo.is_archived:
        return RepositoryResponse.model_validate(repo)
    active = await count_active_repositories(db, organization_id=org.id)
    if not active:
        active = await count_active_repositories(db, owner_id=current_user.id)
    # Restoring an archived repo consumes an active slot — never delete others.
    assert_repo_limit(org.plan, int(active), adding=1)
    await lifecycle.unarchive_repository(db, repo, actor=current_user, plan=org.plan)
    await db.commit()
    await db.refresh(repo)
    return RepositoryResponse.model_validate(repo)


@router.post("/{repository_id}/pause-sync", response_model=RepositoryResponse)
async def pause_repository_sync(
    repository_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> RepositoryResponse:
    from app.services.organizations import get_active_organization
    from app.services import repository_lifecycle as lifecycle

    org = await get_active_organization(db, current_user)
    repo = await _get_org_repo(db, current_user, repository_id, write=True)
    try:
        await lifecycle.pause_sync(db, repo, actor=current_user, plan=org.plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(repo)
    return RepositoryResponse.model_validate(repo)


@router.post("/{repository_id}/resume-sync", response_model=RepositoryResponse)
async def resume_repository_sync(
    repository_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> RepositoryResponse:
    from app.services.organizations import get_active_organization
    from app.services import repository_lifecycle as lifecycle

    org = await get_active_organization(db, current_user)
    repo = await _get_org_repo(db, current_user, repository_id, write=True)
    try:
        await lifecycle.resume_sync(db, repo, actor=current_user, plan=org.plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(repo)
    return RepositoryResponse.model_validate(repo)


@router.delete("/{repository_id}", status_code=status.HTTP_200_OK)
async def delete_repository(
    repository_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """
    Permanently remove the repository from Verspect.

    Deletes all Verspect data for this repository. Never deletes the GitHub repo.
    Releases repository quota after success. Team+ plans receive an audit log entry.
    """
    from app.services.organizations import get_active_organization
    from app.services import repository_lifecycle as lifecycle

    org = await get_active_organization(db, current_user)
    repo = await _get_org_repo(db, current_user, repository_id, write=True)

    async def _delete_webhook(r: Repository) -> None:
        token = github_auth_service.get_user_github_token(current_user)
        client = GitHubAPIClient(token)
        if r.webhook_id:
            await client.delete_webhook(r.owner_login, r.name, r.webhook_id)

    result = await lifecycle.remove_repository(
        db,
        repo,
        actor=current_user,
        plan=org.plan,
        delete_github_webhook=_delete_webhook,
    )
    await db.commit()

    # Filesystem cleanup only after the DB transaction succeeds
    clone_id = result.pop("cleanup_clone_id", None)
    result.pop("local_path_hint", None)
    if clone_id:
        try:
            from app.services.clone import cleanup_repository

            cleanup_repository(str(clone_id))
        except Exception:
            pass
    return result


async def _get_org_repo(
    db: DbSession,
    current_user: CurrentUser,
    repository_id: UUID,
    *,
    write: bool = False,
) -> Repository:
    from app.services.repo_access import get_org_repository

    return await get_org_repository(db, current_user, repository_id, write=write)
