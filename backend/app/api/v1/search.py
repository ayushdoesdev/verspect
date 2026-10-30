"""Global search across dependencies, repositories, files, and functions."""

from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.api.deps.auth import CurrentUser, DbSession
from app.models.dependency import Dependency
from app.models.library_usage import LibraryUsage
from app.models.repository import Repository
from app.schemas.alert import SearchHit, SearchResponse

router = APIRouter()


@router.get("", response_model=SearchResponse)
async def search(
    current_user: CurrentUser,
    db: DbSession,
    q: str = Query(..., min_length=1, max_length=256),
    types: str | None = Query(None, description="Comma-separated: dependency,repository,file,function"),
    limit: int = Query(25, ge=1, le=100),
) -> SearchResponse:
    wanted = {t.strip() for t in types.split(",")} if types else {
        "dependency",
        "repository",
        "file",
        "function",
        "api",
    }
    # api is an alias for symbol/FQN search
    if "api" in wanted:
        wanted.add("function")
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, current_user)
    pattern = f"%{q}%"
    hits: list[SearchHit] = []
    owner_filter = (
        Repository.organization_id == org.id,
        Repository.deleted_at.is_(None),
    )

    if "repository" in wanted:
        repos = (
            await db.execute(
                select(Repository)
                .where(
                    *owner_filter,
                    or_(
                        Repository.full_name.ilike(pattern),
                        Repository.name.ilike(pattern),
                        Repository.description.ilike(pattern),
                    ),
                )
                .limit(limit)
            )
        ).scalars().all()
        for r in repos:
            hits.append(
                SearchHit(
                    type="repository",
                    id=str(r.id),
                    title=r.full_name,
                    subtitle=r.description,
                    url=f"/repositories/{r.id}",
                    meta={"language": r.language, "health_score": r.health_score},
                )
            )

    if "dependency" in wanted:
        deps = (
            await db.execute(
                select(Dependency)
                .join(Repository, Dependency.repository_id == Repository.id)
                .where(
                    *owner_filter,
                    or_(
                        Dependency.package_name.ilike(pattern),
                        Dependency.normalized_name.ilike(pattern),
                        Dependency.summary.ilike(pattern),
                    ),
                )
                .limit(limit)
            )
        ).scalars().all()
        for d in deps:
            hits.append(
                SearchHit(
                    type="dependency",
                    id=str(d.id),
                    title=d.package_name,
                    subtitle=f"{d.current_version or '?'} → {d.latest_version or '?'}",
                    url=f"/dependencies/{d.id}",
                    meta={
                        "status": d.status,
                        "health_score": d.health_score,
                        "repository_id": str(d.repository_id),
                    },
                )
            )

    if "file" in wanted or "function" in wanted:
        conditions = []
        if "file" in wanted:
            conditions.append(LibraryUsage.file_path.ilike(pattern))
        if "function" in wanted:
            conditions.append(LibraryUsage.enclosing_function.ilike(pattern))
            conditions.append(LibraryUsage.symbol.ilike(pattern))
            conditions.append(LibraryUsage.fully_qualified_name.ilike(pattern))

        usages = (
            await db.execute(
                select(LibraryUsage)
                .join(Repository, LibraryUsage.repository_id == Repository.id)
                .where(*owner_filter, or_(*conditions))
                .limit(limit)
            )
        ).scalars().all()
        for u in usages:
            if "file" in wanted and q.lower() in u.file_path.lower():
                hits.append(
                    SearchHit(
                        type="file",
                        id=str(u.id),
                        title=u.file_path,
                        subtitle=f"{u.fully_qualified_name} @ L{u.line}",
                        url=f"/dependencies/{u.dependency_id}?file={u.file_path}",
                        meta={"line": u.line, "package": u.package_name},
                    )
                )
            if "function" in wanted and (
                (u.enclosing_function and q.lower() in u.enclosing_function.lower())
                or q.lower() in u.symbol.lower()
                or q.lower() in u.fully_qualified_name.lower()
            ):
                hits.append(
                    SearchHit(
                        type="function",
                        id=str(u.id),
                        title=u.enclosing_function or u.symbol,
                        subtitle=f"{u.file_path}:{u.line}",
                        url=f"/dependencies/{u.dependency_id}?line={u.line}",
                        meta={
                            "class": u.enclosing_class,
                            "symbol": u.fully_qualified_name,
                        },
                    )
                )

    seen: set[str] = set()
    unique: list[SearchHit] = []
    for h in hits:
        key = f"{h.type}:{h.id}"
        if key not in seen:
            seen.add(key)
            unique.append(h)

    return SearchResponse(query=q, total=len(unique), hits=unique[:limit])
