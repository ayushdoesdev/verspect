"""Persistent rule store — never regenerate existing rules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.migration_engine.cache import MigrationCache, content_hash
from app.migration_engine.models import MigrationRuleBatch, MigrationRuleDTO
from app.models.knowledge import (
    DocumentationSource,
    KnowledgeBaseEntry,
    KnowledgeReleaseNote,
    MigrationExample,
    MigrationRule,
)
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)


class RuleStore:
    def __init__(self, session: Session, cache: Optional[MigrationCache] = None) -> None:
        self.session = session
        self.cache = cache or MigrationCache()

    def get_or_create_kb(
        self,
        package_name: str,
        pypi_url: Optional[str] = None,
        github_url: Optional[str] = None,
    ) -> KnowledgeBaseEntry:
        """Reuse KnowledgeBaseEntry as a cache keyed by (normalized_name, ecosystem).

        Uses INSERT … ON CONFLICT so concurrent simulations / learners never raise
        UniqueViolation on ``uq_kb_normalized_eco``.
        """
        normalized = normalize_package_name(package_name)
        default_pypi = pypi_url or f"https://pypi.org/project/{normalized}/"

        existing = self._fetch_kb(normalized)
        if existing is not None:
            self._enrich_kb_urls(existing, pypi_url=default_pypi, github_url=github_url)
            return existing

        # Atomic create-or-reuse: concurrent workers racing on the same package
        # must not raise UniqueViolation on uq_kb_normalized_eco.
        insert_stmt = (
            pg_insert(KnowledgeBaseEntry)
            .values(
                id=uuid4(),
                package_name=package_name,
                normalized_name=normalized,
                ecosystem="PyPI",
                pypi_url=default_pypi,
                github_url=github_url,
                rule_count=0,
                metadata_json={},
            )
            .on_conflict_do_nothing(constraint="uq_kb_normalized_eco")
            .returning(KnowledgeBaseEntry.id)
        )
        kb_id = self.session.execute(insert_stmt).scalar_one_or_none()
        if kb_id is not None:
            entry = self.session.get(KnowledgeBaseEntry, kb_id)
            logger.info("knowledge_base_created", package=normalized, id=str(kb_id))
        else:
            # Another transaction won the insert — reuse the committed row.
            entry = self._fetch_kb(normalized)
            logger.info("knowledge_base_reused", package=normalized)

        if entry is None:
            raise RuntimeError(f"knowledge_base_upsert_failed package={normalized}")

        self._enrich_kb_urls(entry, pypi_url=default_pypi, github_url=github_url)
        return entry

    def _fetch_kb(self, normalized: str) -> Optional[KnowledgeBaseEntry]:
        return self.session.execute(
            select(KnowledgeBaseEntry).where(
                KnowledgeBaseEntry.normalized_name == normalized,
                KnowledgeBaseEntry.ecosystem == "PyPI",
            )
        ).scalar_one_or_none()

    @staticmethod
    def _enrich_kb_urls(
        entry: KnowledgeBaseEntry,
        *,
        pypi_url: Optional[str],
        github_url: Optional[str],
    ) -> None:
        if github_url and not entry.github_url:
            entry.github_url = github_url
        if pypi_url and not entry.pypi_url:
            entry.pypi_url = pypi_url

    def existing_rules(
        self,
        package_name: str,
        from_version: str,
        to_version: str,
    ) -> list[MigrationRule]:
        normalized = normalize_package_name(package_name)
        return list(
            self.session.execute(
                select(MigrationRule).where(
                    MigrationRule.normalized_name == normalized,
                    MigrationRule.from_version == from_version,
                    MigrationRule.to_version == to_version,
                    MigrationRule.validation_status.in_(["validated", "needs_review", "pending"]),
                )
            ).scalars().all()
        )

    def has_rules(self, package_name: str, from_version: str, to_version: str) -> bool:
        return len(self.existing_rules(package_name, from_version, to_version)) > 0

    def store_rules(
        self,
        batch: MigrationRuleBatch,
        package_name: str,
        from_version: str,
        to_version: str,
        kb: Optional[KnowledgeBaseEntry] = None,
    ) -> list[MigrationRule]:
        """Persist rules. Skip identities that already exist."""
        kb = kb or self.get_or_create_kb(package_name)
        normalized = normalize_package_name(package_name)
        stored: list[MigrationRule] = []
        created = 0

        for dto in batch.rules:
            match_kind = (dto.match_kind or "").strip()
            existing = self.session.execute(
                select(MigrationRule).where(
                    MigrationRule.normalized_name == normalized,
                    MigrationRule.from_version == from_version,
                    MigrationRule.to_version == to_version,
                    MigrationRule.symbol == dto.symbol,
                    MigrationRule.kind == dto.kind,
                    MigrationRule.match_kind == match_kind,
                )
            ).scalar_one_or_none()

            if existing:
                # Refresh structured match metadata from DTO when present
                meta = dict(existing.extra_metadata or {})
                if match_kind:
                    meta["match_kind"] = match_kind
                if dto.unchanged:
                    meta["unchanged"] = True
                if dto.import_fix:
                    meta["import_fix"] = dto.import_fix
                if dto.reference_title:
                    meta["reference_title"] = dto.reference_title
                existing.match_kind = match_kind
                existing.description = dto.description or existing.description
                existing.severity = dto.severity or existing.severity
                existing.confidence = dto.confidence if dto.confidence is not None else existing.confidence
                existing.before = dto.before if dto.before is not None else existing.before
                existing.after = None if dto.unchanged else (dto.after if dto.after is not None else existing.after)
                existing.reason = dto.reason or existing.reason
                existing.official_reference = dto.official_reference or existing.official_reference
                existing.auto_fixable = False if dto.unchanged else bool(dto.auto_fixable)
                existing.estimated_effort = dto.estimated_effort or existing.estimated_effort
                existing.validation_status = dto.validation_status or existing.validation_status
                existing.source_type = dto.source_type or existing.source_type
                existing.source_url = dto.source_url or existing.source_url
                existing.extra_metadata = meta or existing.extra_metadata
                stored.append(existing)
                continue

            meta = {}
            if match_kind:
                meta["match_kind"] = match_kind
            if dto.unchanged:
                meta["unchanged"] = True
            if dto.import_fix:
                meta["import_fix"] = dto.import_fix
            if dto.reference_title:
                meta["reference_title"] = dto.reference_title

            rule = MigrationRule(
                knowledge_base_id=kb.id,
                library=package_name,
                normalized_name=normalized,
                from_version=from_version,
                to_version=to_version,
                symbol=dto.symbol,
                kind=dto.kind,
                match_kind=match_kind,
                description=dto.description,
                severity=dto.severity,
                confidence=dto.confidence,
                before=dto.before,
                after=None if dto.unchanged else dto.after,
                reason=dto.reason,
                official_reference=dto.official_reference,
                auto_fixable=False if dto.unchanged else bool(dto.auto_fixable),
                estimated_effort=dto.estimated_effort,
                validation_status=dto.validation_status or "pending",
                source_type=dto.source_type,
                source_url=dto.source_url,
                content_hash=content_hash(
                    f"{dto.symbol}|{match_kind}|{dto.kind}|{dto.description}|{dto.before}|{dto.after}"
                ),
                extra_metadata=meta or None,
            )
            self.session.add(rule)
            self.session.flush()

            if dto.before and dto.after:
                self.session.add(
                    MigrationExample(
                        rule_id=rule.id,
                        title=f"{dto.symbol} migration",
                        before_code=dto.before,
                        after_code=dto.after,
                        explanation=dto.reason or dto.description,
                        official_reference=dto.official_reference,
                    )
                )
            stored.append(rule)
            created += 1

        kb.rule_count = self.session.execute(
            select(func.count()).select_from(MigrationRule).where(
                MigrationRule.knowledge_base_id == kb.id
            )
        ).scalar_one()
        kb.last_learned_at = datetime.now(timezone.utc)
        self.session.flush()

        # Invalidate cache so next read gets DB truth
        self.cache.set_json(
            self.cache.rules_key(normalized, from_version, to_version),
            [self._to_dto(r).model_dump() for r in stored],
        )
        logger.info(
            "rules_stored",
            package=normalized,
            created=created,
            total=len(stored),
            range=f"{from_version}->{to_version}",
        )
        return stored

    def store_documentation(
        self,
        kb: KnowledgeBaseEntry,
        sources: list[dict],
    ) -> None:
        for src in sources:
            url = src.get("url")
            if not url:
                continue
            existing = self.session.execute(
                select(DocumentationSource).where(
                    DocumentationSource.knowledge_base_id == kb.id,
                    DocumentationSource.url == url,
                    DocumentationSource.source_type == (src.get("source_type") or "docs"),
                )
            ).scalar_one_or_none()
            if existing:
                if src.get("content") and src.get("content_hash") != existing.content_hash:
                    existing.content_excerpt = (src.get("content") or "")[:20000]
                    existing.content_hash = src.get("content_hash")
                    existing.fetched_at = datetime.now(timezone.utc)
                    existing.http_status = src.get("http_status")
                continue
            self.session.add(
                DocumentationSource(
                    knowledge_base_id=kb.id,
                    source_type=src.get("source_type") or "docs",
                    url=url,
                    title=src.get("title"),
                    content_hash=src.get("content_hash"),
                    content_excerpt=(src.get("content") or "")[:20000],
                    fetched_at=datetime.now(timezone.utc),
                    http_status=src.get("http_status"),
                )
            )
        self.session.flush()

    def store_release_notes(self, package_name: str, releases: list[dict]) -> None:
        normalized = normalize_package_name(package_name)
        for rel in releases:
            version = rel.get("version")
            if not version:
                continue
            source = rel.get("source") or "github_release"
            existing = self.session.execute(
                select(KnowledgeReleaseNote).where(
                    KnowledgeReleaseNote.normalized_name == normalized,
                    KnowledgeReleaseNote.version == version,
                    KnowledgeReleaseNote.source == source,
                )
            ).scalar_one_or_none()
            if existing:
                continue
            body = rel.get("body") or ""
            lower = body.lower()
            self.session.add(
                KnowledgeReleaseNote(
                    package_name=package_name,
                    normalized_name=normalized,
                    version=version,
                    source=source,
                    url=rel.get("url"),
                    title=rel.get("title"),
                    body=body[:50000],
                    content_hash=rel.get("content_hash") or content_hash(body),
                    breaking_hints=[
                        line.strip()
                        for line in body.splitlines()
                        if any(k in line.lower() for k in ("breaking", "incompatible", "removed"))
                    ][:20],
                    deprecated_hints=[
                        line.strip()
                        for line in body.splitlines()
                        if "deprecat" in line.lower()
                    ][:20],
                    security_hints=[
                        line.strip()
                        for line in body.splitlines()
                        if any(k in line.lower() for k in ("security", "cve", "vulnerab"))
                    ][:20],
                )
            )
        self.session.flush()

    def rules_as_dto(self, rules: list[MigrationRule]) -> list[MigrationRuleDTO]:
        return [self._to_dto(r) for r in rules]

    @staticmethod
    def _to_dto(rule: MigrationRule) -> MigrationRuleDTO:
        meta = rule.extra_metadata or {}
        return MigrationRuleDTO(
            id=str(rule.id),
            library=rule.library,
            from_version=rule.from_version,
            to_version=rule.to_version,
            symbol=rule.symbol,
            kind=rule.kind,
            description=rule.description,
            severity=rule.severity,
            confidence=rule.confidence,
            before=rule.before,
            after=rule.after,
            reason=rule.reason,
            official_reference=rule.official_reference,
            reference_title=meta.get("reference_title"),
            auto_fixable=rule.auto_fixable,
            estimated_effort=rule.estimated_effort,
            source_type=rule.source_type,
            source_url=rule.source_url,
            validation_status=rule.validation_status,
            match_kind=(rule.match_kind or meta.get("match_kind") or None) or None,
            unchanged=bool(meta.get("unchanged")),
            import_fix=meta.get("import_fix"),
        )
