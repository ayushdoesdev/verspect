"""Python LanguageAnalyzer — deterministic manifests + AST + dependency graph.

Wraps existing ManifestScanner / ASTParser / RepositoryClassifier. Does not call
LLMs and does not invent package or vulnerability facts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

import tomli

from app.core.enums import UsageKind
from app.scanners.analyzers.base import (
    AnalyzerDetection,
    DependencyGraph,
    DependencyGraphEdge,
    DependencyGraphNode,
    LanguageAnalyzer,
)
from app.scanners.ast_parser import ASTParser, ASTScanResult, UsageRecord
from app.scanners.classification import RepositoryClassifier
from app.scanners.manifest import ManifestScanResult, ManifestScanner
from app.scanners.normalize import normalize_package_name, read_text_auto


_IMPORT_KINDS = {UsageKind.IMPORT.value, UsageKind.FROM_IMPORT.value}


class PythonAnalyzer(LanguageAnalyzer):
    language_id = "python"
    display_name = "Python"
    ecosystem = "PyPI"

    def detect(self, repo_path: str | Path) -> AnalyzerDetection:
        classification = RepositoryClassifier(repo_path).classify()
        return AnalyzerDetection(
            classification=classification,
            language_id=classification.language_id or self.language_id,
            package_managers=list(classification.package_managers or []),
        )

    def parse_dependencies(self, repo_path: str | Path) -> ManifestScanResult:
        return ManifestScanner(repo_path).scan()

    def analyze_imports(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> list[UsageRecord]:
        result = self.analyze_api_usage(repo_path, known_packages=known_packages)
        return [u for u in result.usages if u.usage_kind in _IMPORT_KINDS]

    def analyze_api_usage(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> ASTScanResult:
        packages = set(known_packages or [])
        if not packages:
            packages = {
                d.normalized_name for d in self.parse_dependencies(repo_path).merged_by_name()
            }
        return ASTParser(repo_path, known_packages=packages).scan()

    def build_dependency_graph(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> DependencyGraph:
        root = Path(repo_path)
        manifest = self.parse_dependencies(root)
        merged = manifest.merged_by_name()
        nodes = [
            DependencyGraphNode(
                package_name=d.package_name,
                normalized_name=d.normalized_name,
                version=d.version,
                is_direct=d.is_direct,
                is_dev=d.is_dev,
                manifest_source=d.manifest_source,
            )
            for d in merged
        ]
        edges = self._lockfile_edges(root)
        # Keep edges that reference known nodes when possible; still retain lock edges
        # for transitive packages that appear only as children.
        node_names = {n.normalized_name for n in nodes}
        for edge in edges:
            if edge.to_package not in node_names:
                nodes.append(
                    DependencyGraphNode(
                        package_name=edge.to_package,
                        normalized_name=edge.to_package,
                        is_direct=False,
                        manifest_source=edge.source,
                    )
                )
                node_names.add(edge.to_package)
            if edge.from_package not in node_names:
                nodes.append(
                    DependencyGraphNode(
                        package_name=edge.from_package,
                        normalized_name=edge.from_package,
                        is_direct=False,
                        manifest_source=edge.source,
                    )
                )
                node_names.add(edge.from_package)

        packages = set(known_packages or node_names)
        ast_result = ASTParser(root, known_packages=packages).scan() if packages else ASTScanResult()
        used = sorted({normalize_package_name(u.package_name) for u in ast_result.usages})

        return DependencyGraph(nodes=nodes, edges=edges, used_packages=used)

    def _lockfile_edges(self, repo_path: Path) -> list[DependencyGraphEdge]:
        edges: list[DependencyGraphEdge] = []
        skip_dirs = {
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".tox",
            "dist",
            "build",
        }
        for path in repo_path.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            rel = str(path.relative_to(repo_path))
            if path.name == "poetry.lock":
                edges.extend(self._poetry_lock_edges(path, rel))
            elif path.name == "uv.lock":
                edges.extend(self._uv_lock_edges(path, rel))
            elif path.name == "Pipfile.lock":
                edges.extend(self._pipfile_lock_edges(path, rel))
        return edges

    @staticmethod
    def _poetry_lock_edges(path: Path, source: str) -> list[DependencyGraphEdge]:
        data = tomli.loads(read_text_auto(path))
        edges: list[DependencyGraphEdge] = []
        for pkg in data.get("package") or []:
            name = pkg.get("name")
            if not name:
                continue
            parent = normalize_package_name(name)
            deps = pkg.get("dependencies") or {}
            if isinstance(deps, dict):
                for child in deps:
                    if str(child).lower() == "python":
                        continue
                    edges.append(
                        DependencyGraphEdge(
                            from_package=parent,
                            to_package=normalize_package_name(str(child)),
                            source=source,
                        )
                    )
        return edges

    @staticmethod
    def _uv_lock_edges(path: Path, source: str) -> list[DependencyGraphEdge]:
        data = tomli.loads(read_text_auto(path))
        edges: list[DependencyGraphEdge] = []
        for pkg in data.get("package") or []:
            name = pkg.get("name")
            if not name:
                continue
            parent = normalize_package_name(name)
            for dep in pkg.get("dependencies") or []:
                if isinstance(dep, dict):
                    child = dep.get("name")
                else:
                    child = str(dep)
                if not child or str(child).lower() == "python":
                    continue
                edges.append(
                    DependencyGraphEdge(
                        from_package=parent,
                        to_package=normalize_package_name(str(child)),
                        source=source,
                    )
                )
        return edges

    @staticmethod
    def _pipfile_lock_edges(path: Path, source: str) -> list[DependencyGraphEdge]:
        """Pipfile.lock does not encode a full graph; return empty edges."""
        try:
            json.loads(read_text_auto(path))
        except Exception:
            return []
        return []
