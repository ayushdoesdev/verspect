"""PHP analyzer using deterministic Composer and conservative source parsing.

Composer JSON/lock data is authoritative. PHP usage matching is intentionally
limited: namespace imports are mapped only when the Composer vendor uniquely
identifies a known package, and require/include expressions are accepted only
for literal ``vendor/<vendor>/<package>/...`` paths. Aliases, autoload maps,
dynamic expressions, and runtime class loading are not resolved.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional, Sequence

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


_SKIP_DIRS = {".git", "vendor", "node_modules", "dist", "build", "cache"}
_USE_RE = re.compile(
    r"^\s*use\s+(?P<module>[A-Za-z_\x80-\xff][\w\x80-\xff]*(?:\\[\w\x80-\xff]+)+)"
    r"(?:\s+as\s+(?P<alias>[A-Za-z_]\w*))?\s*;"
)
_REQUIRE_RE = re.compile(
    r"""\b(?P<style>require|require_once|include|include_once)\s*(?:\(\s*)?"""
    r"""["'](?P<path>vendor/(?P<vendor>[^/"']+)/(?P<package>[^/"']+)(?:/[^"']*)?)["']"""
)


def normalize_composer_name(name: str) -> str:
    return (name or "").strip().lower()


class PHPAnalyzer(LanguageAnalyzer):
    language_id = "php"
    display_name = "PHP"
    ecosystem = "Packagist"

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
        direct: dict[str, bool] = {}
        for path in self._find_files(root, "composer.json"):
            rel = str(path.relative_to(root))
            result.files_found.append(rel)
            try:
                dependencies, _project = self._parse_composer_json(path)
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            for dependency in dependencies:
                dependency.manifest_source = rel
                direct[dependency.normalized_name] = dependency.is_dev
            result.dependencies.extend(dependencies)
        for path in self._find_files(root, "composer.lock"):
            rel = str(path.relative_to(root))
            result.files_found.append(rel)
            try:
                data = json.loads(read_text_auto(path))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            for section, section_dev in (("packages", False), ("packages-dev", True)):
                for package in data.get(section) or []:
                    if not isinstance(package, dict) or not package.get("name"):
                        continue
                    name = str(package["name"])
                    normalized = normalize_composer_name(name)
                    version = str(package.get("version") or "") or None
                    result.dependencies.append(
                        ParsedDependency(
                            package_name=name,
                            normalized_name=normalized,
                            version=version,
                            constraint=f"=={version}" if version else None,
                            is_direct=normalized in direct,
                            is_dev=direct.get(normalized, section_dev),
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
            normalize_composer_name(name)
            for name in (
                known_packages
                or [dep.normalized_name for dep in self.parse_dependencies(root).merged_by_name()]
            )
        }
        result = ASTScanResult()
        if not root.exists():
            return result
        for path in self._walk(root):
            if path.suffix.lower() != ".php":
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
                match = _USE_RE.match(line)
                if match:
                    module = match.group("module")
                    package = self._package_for_namespace(module, known)
                    if package:
                        self._append_usage(
                            result, package, module, rel, line_no,
                            original.find(module), original, "namespace_use",
                            alias=match.group("alias"),
                        )
                for require_match in _REQUIRE_RE.finditer(line):
                    package = normalize_composer_name(
                        f"{require_match.group('vendor')}/{require_match.group('package')}"
                    )
                    if package not in known:
                        continue
                    module = require_match.group("path")
                    self._append_usage(
                        result, package, module, rel, line_no,
                        require_match.start("path"), original,
                        require_match.group("style"),
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
        for path in self._find_files(root, "composer.json"):
            rel = str(path.relative_to(root))
            try:
                dependencies, project = self._parse_composer_json(path)
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            if project:
                project = normalize_composer_name(project)
                if project not in node_names:
                    nodes.append(DependencyGraphNode(project, project, manifest_source=rel))
                    node_names.add(project)
                edges.extend(
                    DependencyGraphEdge(project, dep.normalized_name, source=rel)
                    for dep in dependencies
                )
        for path in self._find_files(root, "composer.lock"):
            rel = str(path.relative_to(root))
            try:
                data = json.loads(read_text_auto(path))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            for section in ("packages", "packages-dev"):
                for package in data.get(section) or []:
                    if not isinstance(package, dict) or not package.get("name"):
                        continue
                    parent = normalize_composer_name(str(package["name"]))
                    for child in (package.get("require") or {}):
                        normalized = normalize_composer_name(str(child))
                        if "/" in normalized and normalized in node_names:
                            edges.append(DependencyGraphEdge(parent, normalized, source=rel))
        usages = self.analyze_api_usage(root, known_packages=known_packages or sorted(node_names))
        unique = {
            (edge.from_package, edge.to_package, edge.source): edge for edge in edges
        }
        return DependencyGraph(
            nodes=nodes,
            edges=list(unique.values()),
            used_packages=sorted({usage.package_name for usage in usages.usages}),
        )

    @staticmethod
    def _parse_composer_json(path: Path) -> tuple[list[ParsedDependency], str | None]:
        data = json.loads(read_text_auto(path))
        dependencies: list[ParsedDependency] = []
        for section, is_dev in (("require", False), ("require-dev", True)):
            block = data.get(section) or {}
            if not isinstance(block, dict):
                continue
            for name, constraint in block.items():
                normalized = normalize_composer_name(str(name))
                if "/" not in normalized:
                    continue
                dependencies.append(
                    ParsedDependency(
                        package_name=str(name),
                        normalized_name=normalized,
                        constraint=str(constraint) if constraint is not None else None,
                        is_direct=True,
                        is_dev=is_dev,
                        ecosystem="Packagist",
                    )
                )
        return dependencies, str(data.get("name") or "") or None

    @staticmethod
    def _package_for_namespace(module: str, known: set[str]) -> str | None:
        vendor = module.split("\\", 1)[0].lower()
        candidates = [name for name in known if name.split("/", 1)[0] == vendor]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            return None
        tokens = {part.lower() for part in module.split("\\")}
        matched = [
            name for name in candidates
            if set(re.split(r"[-_.]+", name.split("/", 1)[1])).issubset(tokens)
        ]
        return matched[0] if len(matched) == 1 else None

    @staticmethod
    def _append_usage(
        result: ASTScanResult,
        package: str,
        module: str,
        file_path: str,
        line_no: int,
        column: int,
        line: str,
        style: str,
        *,
        alias: str | None = None,
    ) -> None:
        result.usages.append(
            UsageRecord(
                package_name=package,
                module_path=module,
                symbol=alias or re.split(r"[\\/]", module)[-1],
                fully_qualified_name=module,
                usage_kind=UsageKind.IMPORT.value,
                file_path=file_path,
                line=line_no,
                column=max(0, column),
                end_line=line_no,
                end_column=max(0, column) + len(module),
                code_snippet=line.rstrip()[:500],
                alias=alias,
                context={
                    "parser": "deterministic_import_syntax",
                    "import_style": style,
                    "limitation": "literal_vendor_paths_and_unambiguous_namespaces_only",
                },
            )
        )

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
            elif line.startswith("//", index) or line.startswith("#", index):
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
        return sorted(path for path in PHPAnalyzer._walk(root) if path.name == name)
