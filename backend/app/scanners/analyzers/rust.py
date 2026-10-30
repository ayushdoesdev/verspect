"""Rust analyzer using deterministic Cargo manifest, lockfile, and import parsing.

Cargo TOML is parsed without executing Cargo. Source analysis intentionally
recognizes only simple, single-line ``use crate_name::...`` and
``extern crate crate_name`` declarations. Macro-expanded imports, renamed
symbols, and API calls are not inferred.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Sequence

import tomli

from app.core.enums import UsageKind
from app.scanners.analyzers.base import (
    AnalyzerDetection,
    DependencyGraph,
    DependencyGraphEdge,
    DependencyGraphNode,
    LanguageAnalyzer,
)
from app.scanners.ast_parser import ASTScanResult, UsageRecord
from app.scanners.classification import RepositoryClassifier
from app.scanners.manifest import ManifestScanResult, ParsedDependency
from app.scanners.normalize import read_text_auto


_SKIP_DIRS = {".git", "target", "vendor", "node_modules", "dist", "build"}
_USE_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?use\s+(?P<module>[A-Za-z_]\w*(?:::[^;]+)?)\s*;")
_EXTERN_RE = re.compile(
    r"^\s*extern\s+crate\s+(?P<module>[A-Za-z_]\w*)(?:\s+as\s+(?P<alias>[A-Za-z_]\w*))?\s*;"
)


def normalize_crate_name(name: str) -> str:
    return (name or "").strip().lower().replace("_", "-")


class RustAnalyzer(LanguageAnalyzer):
    language_id = "rust"
    display_name = "Rust"
    ecosystem = "crates.io"

    def detect(self, repo_path: str | Path) -> AnalyzerDetection:
        classification = RepositoryClassifier(repo_path).classify()
        return AnalyzerDetection(
            classification=classification,
            language_id=classification.language_id or self.language_id,
            package_managers=list(classification.package_managers or []),
        )

    def parse_dependencies(self, repo_path: str | Path) -> ManifestScanResult:
        root = Path(repo_path)
        result = ManifestScanResult()
        if not root.exists():
            return result
        direct_names: dict[str, bool] = {}
        project_names: set[str] = set()
        for path in self._find_files(root, "Cargo.toml"):
            rel = str(path.relative_to(root))
            result.files_found.append(rel)
            try:
                dependencies, project = self._parse_manifest(path)
            except (OSError, tomli.TOMLDecodeError):
                continue
            for dependency in dependencies:
                dependency.manifest_source = rel
                direct_names[dependency.normalized_name] = (
                    direct_names.get(dependency.normalized_name, False)
                    or dependency.is_dev
                )
            if project:
                project_names.add(normalize_crate_name(project))
            result.dependencies.extend(dependencies)
        for path in self._find_files(root, "Cargo.lock"):
            rel = str(path.relative_to(root))
            result.files_found.append(rel)
            try:
                packages = self._lock_packages(path)
            except (OSError, tomli.TOMLDecodeError):
                continue
            for package in packages:
                name = str(package.get("name") or "")
                version = str(package.get("version") or "") or None
                if not name or normalize_crate_name(name) in project_names:
                    continue
                normalized = normalize_crate_name(name)
                result.dependencies.append(
                    ParsedDependency(
                        package_name=name,
                        normalized_name=normalized,
                        version=version,
                        constraint=f"=={version}" if version else None,
                        is_direct=normalized in direct_names,
                        is_dev=direct_names.get(normalized, False),
                        manifest_source=rel,
                        ecosystem=self.ecosystem,
                    )
                )
        result.files_found.sort()
        return result

    def analyze_imports(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> list[UsageRecord]:
        return self.analyze_api_usage(repo_path, known_packages=known_packages).usages

    def analyze_api_usage(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> ASTScanResult:
        root = Path(repo_path)
        known = {
            normalize_crate_name(name)
            for name in (
                known_packages
                or [dep.normalized_name for dep in self.parse_dependencies(root).merged_by_name()]
            )
        }
        import_names = {
            package.replace("-", "_"): package
            for package in known
        }
        for manifest_path in self._find_files(root, "Cargo.toml"):
            try:
                manifest_dependencies, _project = self._parse_manifest(manifest_path)
            except (OSError, tomli.TOMLDecodeError):
                continue
            for dependency in manifest_dependencies:
                alias = (
                    dependency.marker.removeprefix("cargo_alias=")
                    if dependency.marker and dependency.marker.startswith("cargo_alias=")
                    else dependency.package_name
                )
                if dependency.normalized_name in known:
                    import_names[alias.replace("-", "_")] = dependency.normalized_name
        result = ASTScanResult()
        if not root.exists():
            return result
        for path in self._walk(root):
            if path.suffix.lower() != ".rs":
                continue
            try:
                text = read_text_auto(path)
            except OSError:
                result.files_failed += 1
                continue
            result.files_parsed += 1
            rel = str(path.relative_to(root))
            in_block_comment = False
            for line_no, original in enumerate(text.splitlines(), start=1):
                line, in_block_comment = self._strip_comments(original, in_block_comment)
                match = _EXTERN_RE.match(line)
                style = "extern_crate"
                if match is None:
                    match = _USE_RE.match(line)
                    style = "use"
                if match is None:
                    continue
                module = match.group("module").strip()
                root_name = module.split("::", 1)[0]
                package = import_names.get(root_name)
                if package is None:
                    continue
                alias = match.groupdict().get("alias")
                column = original.find(root_name)
                result.usages.append(
                    UsageRecord(
                        package_name=package,
                        module_path=module,
                        symbol=alias or module.rsplit("::", 1)[-1],
                        fully_qualified_name=module,
                        usage_kind=UsageKind.IMPORT.value,
                        file_path=rel,
                        line=line_no,
                        column=max(0, column),
                        end_line=line_no,
                        end_column=max(0, column) + len(module),
                        code_snippet=original.rstrip()[:500],
                        alias=alias,
                        context={
                            "parser": "deterministic_import_syntax",
                            "import_style": style,
                            "limitation": "simple_imports_only_no_rust_ast_or_macro_expansion",
                        },
                    )
                )
        return result

    def build_dependency_graph(
        self,
        repo_path: str | Path,
        *,
        known_packages: Optional[Sequence[str]] = None,
    ) -> DependencyGraph:
        root = Path(repo_path)
        merged = self.parse_dependencies(root).merged_by_name()
        nodes = [
            DependencyGraphNode(
                package_name=dep.package_name,
                normalized_name=dep.normalized_name,
                version=dep.version,
                is_direct=dep.is_direct,
                is_dev=dep.is_dev,
                manifest_source=dep.manifest_source,
            )
            for dep in merged
        ]
        node_names = {node.normalized_name for node in nodes}
        edges: list[DependencyGraphEdge] = []
        for path in self._find_files(root, "Cargo.toml"):
            rel = str(path.relative_to(root))
            try:
                dependencies, project = self._parse_manifest(path)
            except (OSError, tomli.TOMLDecodeError):
                continue
            if project:
                project = normalize_crate_name(project)
                if project not in node_names:
                    nodes.append(
                        DependencyGraphNode(
                            package_name=project,
                            normalized_name=project,
                            manifest_source=rel,
                        )
                    )
                    node_names.add(project)
                edges.extend(
                    DependencyGraphEdge(project, dep.normalized_name, source=rel)
                    for dep in dependencies
                )
        for path in self._find_files(root, "Cargo.lock"):
            rel = str(path.relative_to(root))
            try:
                packages = self._lock_packages(path)
            except (OSError, tomli.TOMLDecodeError):
                continue
            for package in packages:
                parent = normalize_crate_name(str(package.get("name") or ""))
                if not parent:
                    continue
                for raw_child in package.get("dependencies") or []:
                    child = normalize_crate_name(str(raw_child).split()[0])
                    if child:
                        edges.append(DependencyGraphEdge(parent, child, source=rel))
        usages = self.analyze_api_usage(root, known_packages=known_packages or sorted(node_names))
        unique = {
            (edge.from_package, edge.to_package, edge.source): edge for edge in edges
        }
        return DependencyGraph(
            nodes=nodes,
            edges=list(unique.values()),
            used_packages=sorted({usage.package_name for usage in usages.usages}),
        )

    @classmethod
    def _parse_manifest(cls, path: Path) -> tuple[list[ParsedDependency], str | None]:
        data = tomli.loads(read_text_auto(path))
        dependencies: list[ParsedDependency] = []
        for section, is_dev in (
            ("dependencies", False),
            ("dev-dependencies", True),
            ("build-dependencies", False),
        ):
            dependencies.extend(cls._dependency_table(data.get(section), is_dev=is_dev))
        for target in (data.get("target") or {}).values():
            if not isinstance(target, dict):
                continue
            for section, is_dev in (
                ("dependencies", False),
                ("dev-dependencies", True),
                ("build-dependencies", False),
            ):
                dependencies.extend(cls._dependency_table(target.get(section), is_dev=is_dev))
        project = str((data.get("package") or {}).get("name") or "") or None
        return dependencies, project

    @staticmethod
    def _dependency_table(table: Any, *, is_dev: bool) -> list[ParsedDependency]:
        parsed: list[ParsedDependency] = []
        if not isinstance(table, dict):
            return parsed
        for alias, spec in table.items():
            package = str(spec.get("package") or alias) if isinstance(spec, dict) else str(alias)
            constraint = (
                str(spec.get("version")) if isinstance(spec, dict) and spec.get("version") else
                str(spec) if isinstance(spec, str) else None
            )
            marker = f"cargo_alias={alias}" if package != alias else None
            parsed.append(
                ParsedDependency(
                    package_name=package,
                    normalized_name=normalize_crate_name(package),
                    constraint=constraint,
                    marker=marker,
                    is_dev=is_dev,
                    is_direct=True,
                    ecosystem="crates.io",
                )
            )
        return parsed

    @staticmethod
    def _lock_packages(path: Path) -> list[dict[str, Any]]:
        data = tomli.loads(read_text_auto(path))
        return [item for item in data.get("package") or [] if isinstance(item, dict)]

    @staticmethod
    def _strip_comments(line: str, in_block: bool) -> tuple[str, bool]:
        output: list[str] = []
        index = 0
        while index < len(line):
            if in_block:
                end = line.find("*/", index)
                if end < 0:
                    return "".join(output), True
                index = end + 2
                in_block = False
            elif line.startswith("/*", index):
                in_block = True
                index += 2
            elif line.startswith("//", index):
                break
            else:
                output.append(line[index])
                index += 1
        return "".join(output), in_block

    @staticmethod
    def _walk(root: Path):
        for path in root.rglob("*"):
            if path.is_file() and not any(
                part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]
            ):
                yield path

    @staticmethod
    def _find_files(root: Path, name: str) -> list[Path]:
        return sorted(path for path in RustAnalyzer._walk(root) if path.name == name)
