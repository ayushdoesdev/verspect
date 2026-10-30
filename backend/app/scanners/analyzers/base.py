"""Language-agnostic analyzer contracts.

Deterministic analysis stages (manifests, imports, API usage, dependency graphs)
belong behind this interface. Enrichment (PyPI/OSV/license/health) stays in the
scan task until language-specific registries exist.

Additional analyzers implement the same ABC without changing
Upgrade Simulator / Migration Assistant consumption of Dependency + LibraryUsage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from app.scanners.ast_parser import ASTScanResult, UsageRecord
from app.scanners.classification import ClassificationResult
from app.scanners.manifest import ManifestScanResult, ParsedDependency


@dataclass
class DependencyGraphNode:
    package_name: str
    normalized_name: str
    version: Optional[str] = None
    is_direct: bool = True
    is_dev: bool = False
    manifest_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyGraphEdge:
    """Directed edge: `from_package` depends on `to_package`."""

    from_package: str
    to_package: str
    relationship: str = "depends_on"
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyGraph:
    """Evidence-backed package relationship graph (not an AI inference)."""

    nodes: list[DependencyGraphNode] = field(default_factory=list)
    edges: list[DependencyGraphEdge] = field(default_factory=list)
    used_packages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "used_packages": list(self.used_packages),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


@dataclass
class AnalyzerDetection:
    """Optional re-export of classification for analyzer consumers."""

    classification: ClassificationResult
    language_id: str
    package_managers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language_id": self.language_id,
            "package_managers": self.package_managers,
            "classification": self.classification.to_dict(),
        }


class LanguageAnalyzer(ABC):
    """Common interface for per-language deterministic analysis."""

    language_id: str
    display_name: str
    ecosystem: str

    @abstractmethod
    def detect(self, repo_path: str | Path) -> AnalyzerDetection:
        """Detect language / package managers for this repository."""

    @abstractmethod
    def parse_dependencies(self, repo_path: str | Path) -> ManifestScanResult:
        """Parse dependency manifests / lockfiles. Never use an LLM."""

    @abstractmethod
    def analyze_imports(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> list[UsageRecord]:
        """Return import / from-import usage records only."""

    @abstractmethod
    def analyze_api_usage(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> ASTScanResult:
        """Full API usage index (imports + calls + classes + decorators, …)."""

    @abstractmethod
    def build_dependency_graph(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> DependencyGraph:
        """Build package nodes/edges from manifests, lockfiles, and usage evidence."""

    def parse_dependencies_merged(self, repo_path: str | Path) -> list[ParsedDependency]:
        return self.parse_dependencies(repo_path).merged_by_name()
