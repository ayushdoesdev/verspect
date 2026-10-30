"""Language-specific scan pipeline abstraction.

Upgrade Simulator, AI Migration Assistant, and frontend dependency APIs
consume Dependency / LibraryUsage records produced by implemented
pipelines. Unsupported languages must never fabricate
those records — they return a structured NotYetSupported outcome instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.enums import LanguageSupportStatus
from app.scanners.classification import ClassificationResult


@dataclass
class NotYetSupportedResult:
    """Structured result for detected but unimplemented languages."""

    classification: ClassificationResult
    result: str = "not_yet_supported"
    status: str = "completed"

    def to_summary(self) -> dict[str, Any]:
        return {
            "result": self.result,
            "classification": self.classification.to_dict(),
            "message": self.classification.message,
        }


@dataclass
class PipelineContext:
    """Opaque context passed into language pipelines.

    Concrete pipelines may use local_path and classification; the Celery
    scan task retains ownership of DB sessions and shared enrichment stages.
    """

    local_path: str
    classification: ClassificationResult
    repository_id: str
    scan_id: str
    extra: dict[str, Any] = field(default_factory=dict)


class LanguagePipeline(ABC):
    """Base class for per-language scan pipelines."""

    language_id: str
    display_name: str
    support_status: LanguageSupportStatus

    @property
    def is_fully_supported(self) -> bool:
        return self.support_status == LanguageSupportStatus.FULLY_SUPPORTED

    @property
    def can_analyze(self) -> bool:
        """True when an implemented analyzer/pipeline can process this language."""
        return self.support_status in {
            LanguageSupportStatus.FULLY_SUPPORTED,
            LanguageSupportStatus.SUPPORTED,
        }

    @property
    def support_label(self) -> str:
        return {
            LanguageSupportStatus.FULLY_SUPPORTED: "Fully Supported",
            LanguageSupportStatus.SUPPORTED: "Supported",
            LanguageSupportStatus.COMING_SOON: "Coming Soon",
            LanguageSupportStatus.UNKNOWN: "Unknown",
        }[self.support_status]

    def not_yet_supported(
        self, classification: ClassificationResult
    ) -> NotYetSupportedResult:
        return NotYetSupportedResult(classification=classification)

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """Machine-readable pipeline metadata for APIs / debugging."""


class FullySupportedPipeline(LanguagePipeline):
    """Python-depth implementation (AST usage + deterministic upgrade catalog)."""

    support_status = LanguageSupportStatus.FULLY_SUPPORTED


class SupportedPipeline(LanguagePipeline):
    """Implemented analyzer without Python-depth upgrade catalog coverage."""

    support_status = LanguageSupportStatus.SUPPORTED


class ComingSoonPipeline(LanguagePipeline):
    """Detected language with no analysis implementation yet."""

    support_status = LanguageSupportStatus.COMING_SOON

    def __init__(self, language_id: str, display_name: str) -> None:
        self.language_id = language_id
        self.display_name = display_name

    def describe(self) -> dict[str, Any]:
        return {
            "language_id": self.language_id,
            "display_name": self.display_name,
            "support_status": self.support_status.value,
            "support_label": self.support_label,
            "implemented": False,
        }

    def run_unsupported(
        self, classification: ClassificationResult
    ) -> NotYetSupportedResult:
        return self.not_yet_supported(classification)
