"""Library registry — tracks which packages have been learned (no hardcoded libs)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeBaseEntry
from app.scanners.normalize import normalize_package_name


class LibraryRegistry:
    """Discoverability layer over the knowledge base — entirely data-driven."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def is_known(self, package_name: str) -> bool:
        normalized = normalize_package_name(package_name)
        entry = self.session.execute(
            select(KnowledgeBaseEntry).where(
                KnowledgeBaseEntry.normalized_name == normalized
            )
        ).scalar_one_or_none()
        return entry is not None and (entry.rule_count or 0) > 0

    def get(self, package_name: str) -> Optional[KnowledgeBaseEntry]:
        normalized = normalize_package_name(package_name)
        return self.session.execute(
            select(KnowledgeBaseEntry).where(
                KnowledgeBaseEntry.normalized_name == normalized
            )
        ).scalar_one_or_none()

    def list_learned(self, limit: int = 100) -> list[KnowledgeBaseEntry]:
        return list(
            self.session.execute(
                select(KnowledgeBaseEntry)
                .where(KnowledgeBaseEntry.rule_count > 0)
                .order_by(KnowledgeBaseEntry.last_learned_at.desc().nullslast())
                .limit(limit)
            ).scalars().all()
        )
