"""SQLAlchemy models for the Universal Migration Knowledge Base."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeBaseEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-library knowledge base root — grows as libraries are discovered."""

    __tablename__ = "knowledge_base_entries"
    __table_args__ = (
        UniqueConstraint("normalized_name", "ecosystem", name="uq_kb_normalized_eco"),
    )

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ecosystem: Mapped[str] = mapped_column(String(64), default="PyPI", nullable=False)
    pypi_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    docs_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_learned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_release_checked: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    rules: Mapped[list["MigrationRule"]] = relationship(
        "MigrationRule",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    documentation_sources: Mapped[list["DocumentationSource"]] = relationship(
        "DocumentationSource",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DocumentationSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Fetched documentation / changelog / migration guide sources."""

    __tablename__ = "documentation_sources"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id",
            "url",
            "source_type",
            name="uq_doc_sources_kb_url_type",
        ),
    )

    knowledge_base_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_base_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # docs | changelog | migration_guide | github_release | pypi | readme
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    content_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    knowledge_base: Mapped["KnowledgeBaseEntry"] = relationship(
        "KnowledgeBaseEntry",
        back_populates="documentation_sources",
    )


class KnowledgeReleaseNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Library-level release notes (not repo-specific)."""

    __tablename__ = "knowledge_release_notes"
    __table_args__ = (
        UniqueConstraint(
            "normalized_name",
            "version",
            "source",
            name="uq_knowledge_release_notes_pkg_ver_src",
        ),
    )

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="github")
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    breaking_hints: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    deprecated_hints: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    security_hints: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)


class MigrationRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Universal migration rule — one schema for every library."""

    __tablename__ = "migration_rules"
    __table_args__ = (
        UniqueConstraint(
            "normalized_name",
            "from_version",
            "to_version",
            "symbol",
            "kind",
            "match_kind",
            name="uq_migration_rules_identity",
        ),
    )

    knowledge_base_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_base_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    library: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    to_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    symbol: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # removed | deprecated | renamed | signature_change | behavior_change | import_path_change | security | performance
    # Distinguishes rules that share symbol+kind (e.g. BaseModel import vs inheritance).
    match_kind: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="medium", nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    before: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    official_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    auto_fixable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_effort: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    # trivial | low | medium | high | very_high

    validation_status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    # pending | validated | rejected | needs_review

    source_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    knowledge_base: Mapped[Optional["KnowledgeBaseEntry"]] = relationship(
        "KnowledgeBaseEntry",
        back_populates="rules",
    )
    examples: Mapped[list["MigrationExample"]] = relationship(
        "MigrationExample",
        back_populates="rule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MigrationExample(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Concrete before/after code examples for a migration rule."""

    __tablename__ = "migration_examples"

    rule_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("migration_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    before_code: Mapped[str] = mapped_column(Text, nullable=False)
    after_code: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(32), default="python", nullable=False)
    official_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rule: Mapped["MigrationRule"] = relationship("MigrationRule", back_populates="examples")


class MigrationEngineReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Report produced by the Universal Migration Engine for a dependency upgrade."""

    __tablename__ = "migration_engine_reports"

    dependency_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    simulation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("upgrade_simulations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_version: Mapped[str] = mapped_column(String(64), nullable=False)
    to_version: Mapped[str] = mapped_column(String(64), nullable=False)

    readiness_score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    migration_difficulty: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    migration_time_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    security_improvement: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    performance_improvement: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    technical_debt_reduction: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    affected_files: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    affected_symbols: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    matched_rule_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    auto_fix_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manual_fix_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    official_references: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    scoring_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    patches: Mapped[list["PatchSuggestion"]] = relationship(
        "PatchSuggestion",
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PatchSuggestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Suggested code patch grounded in a migration rule + AST usage."""

    __tablename__ = "patch_suggestions"

    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("migration_engine_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("migration_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    current_code: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_code: Mapped[str] = mapped_column(Text, nullable=False)
    unified_diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    official_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_fixable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    validation_status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    validation_errors: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    report: Mapped["MigrationEngineReport"] = relationship(
        "MigrationEngineReport",
        back_populates="patches",
    )


class ValidationHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit trail for rule and patch validation."""

    __tablename__ = "validation_history"

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # rule | patch
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    validator: Mapped[str] = mapped_column(String(64), nullable=False)
    # ast | black | ruff | schema | ai_grounding
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # passed | failed | skipped
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
