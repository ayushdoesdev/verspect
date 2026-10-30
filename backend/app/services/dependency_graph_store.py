"""Persist dependency graph edges from LanguageAnalyzer output."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.dependency import Dependency
from app.models.dependency_relationship import DependencyRelationship
from app.scanners.analyzers.base import DependencyGraph
from app.scanners.normalize import normalize_package_name


def resolve_graph_endpoint(
    dep_by_norm: dict[str, Dependency],
    name: str,
) -> Dependency | None:
    """Match an analyzer graph node to a persisted dependency.

    Analyzer keys are ecosystem-native (Go module paths, Maven coordinates,
    npm scopes). PEP 503 hyphenation is a fallback for PyPI only — applying it
    first drops non-Python edges.
    """
    raw = (name or "").strip()
    if not raw:
        return None
    for key in (raw, raw.lower(), normalize_package_name(raw)):
        found = dep_by_norm.get(key)
        if found is not None:
            return found
    return None


def persist_dependency_graph(
    session: Session,
    *,
    repository_id: UUID,
    graph: DependencyGraph,
    dep_by_norm: dict[str, Dependency],
) -> int:
    """
    Replace repository relationship edges with analyzer graph edges.

    Only persists edges where both endpoints resolve to Dependency rows.
    Returns number of edges written.
    """
    session.execute(
        delete(DependencyRelationship).where(
            DependencyRelationship.repository_id == repository_id
        )
    )
    session.flush()

    written = 0
    seen: set[tuple[UUID, UUID, str]] = set()
    for edge in graph.edges:
        parent = resolve_graph_endpoint(dep_by_norm, edge.from_package)
        child = resolve_graph_endpoint(dep_by_norm, edge.to_package)
        if parent is None or child is None or parent.id == child.id:
            continue
        key = (parent.id, child.id, edge.relationship or "depends_on")
        if key in seen:
            continue
        seen.add(key)
        session.add(
            DependencyRelationship(
                repository_id=repository_id,
                parent_dependency_id=parent.id,
                child_dependency_id=child.id,
                edge_type=edge.relationship or "depends_on",
                source=(edge.source or "")[:255] or None,
            )
        )
        written += 1
    session.flush()
    return written


def introduced_by_paths(
    session: Session,
    *,
    repository_id: UUID,
    dependency_id: UUID,
) -> list[dict]:
    """Return parent packages that directly depend on this dependency."""
    rows = (
        session.execute(
            select(DependencyRelationship, Dependency)
            .join(
                Dependency,
                Dependency.id == DependencyRelationship.parent_dependency_id,
            )
            .where(
                DependencyRelationship.repository_id == repository_id,
                DependencyRelationship.child_dependency_id == dependency_id,
            )
        )
        .all()
    )
    out: list[dict] = []
    for rel, parent in rows:
        out.append(
            {
                "parent_package": parent.package_name,
                "parent_dependency_id": str(parent.id),
                "relationship": rel.edge_type,
                "source": rel.source,
            }
        )
    return out
