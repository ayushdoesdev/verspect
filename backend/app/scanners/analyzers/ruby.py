"""Ruby analyzer using deterministic Bundler files and literal require parsing.

Gemfile support is limited to literal ``gem "name", "constraint"`` calls.
Gemfile.lock provides exact versions and dependency edges. Ruby source parsing
recognizes single-line literal ``require`` and ``require_relative`` calls; it
does not execute Ruby, inspect gemspecs, or resolve dynamic load paths.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Sequence

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


_SKIP_DIRS = {".git", "vendor", ".bundle", "node_modules", "dist", "build"}
_GEM_RE = re.compile(
    r"""^\s*gem\s*(?:\(\s*)?["'](?P<name>[^"']+)["']"""
    r"""(?:\s*,\s*["'](?P<constraint>[^"']+)["'])?"""
)
_REQUIRE_RE = re.compile(
    r"""^\s*(?P<style>require|require_relative)\s*(?:\(\s*)?["'](?P<module>[^"']+)["']"""
)
_LOCK_SPEC_RE = re.compile(r"^ {4}(?P<name>[A-Za-z0-9_.-]+) \((?P<version>[^)]+)\)")
_LOCK_CHILD_RE = re.compile(r"^ {6}(?P<name>[A-Za-z0-9_.-]+)(?: \([^)]+\))?")


def normalize_gem_name(name: str) -> str:
    return (name or "").strip().lower()


class RubyAnalyzer(LanguageAnalyzer):
    language_id = "ruby"
    display_name = "Ruby"
    ecosystem = "RubyGems"

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
        for path in self._find_files(root, "Gemfile"):
            rel = str(path.relative_to(root))
            result.files_found.append(rel)
            try:
                dependencies = self._parse_gemfile(path)
            except OSError:
                continue
            for dependency in dependencies:
                dependency.manifest_source = rel
                direct[dependency.normalized_name] = dependency.is_dev
            result.dependencies.extend(dependencies)
        for path in self._find_files(root, "Gemfile.lock"):
            rel = str(path.relative_to(root))
            result.files_found.append(rel)
            try:
                specs, lock_direct, _edges = self._parse_lock(path)
            except OSError:
                continue
            for name in lock_direct:
                direct.setdefault(name, False)
            for name, version in specs.items():
                result.dependencies.append(
                    ParsedDependency(
                        package_name=name,
                        normalized_name=normalize_gem_name(name),
                        version=version,
                        constraint=f"=={version}",
                        is_direct=normalize_gem_name(name) in direct,
                        is_dev=direct.get(normalize_gem_name(name), False),
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
            normalize_gem_name(name)
            for name in (
                known_packages
                or [dep.normalized_name for dep in self.parse_dependencies(root).merged_by_name()]
            )
        }
        aliases: dict[str, str] = {}
        for package in sorted(known):
            for key in {package, package.replace("-", "_"), package.replace("_", "-")}:
                aliases.setdefault(key, package)
        result = ASTScanResult()
        if not root.exists():
            return result
        for path in self._walk(root):
            if path.suffix.lower() != ".rb":
                continue
            try:
                text = read_text_auto(path)
            except OSError:
                result.files_failed += 1
                continue
            result.files_parsed += 1
            rel = str(path.relative_to(root))
            for line_no, original in enumerate(text.splitlines(), start=1):
                line = original.split("#", 1)[0]
                match = _REQUIRE_RE.match(line)
                if not match:
                    continue
                module = match.group("module")
                root_name = module.split("/", 1)[0].lower()
                package = aliases.get(root_name)
                if package is None:
                    continue
                column = original.find(module)
                result.usages.append(
                    UsageRecord(
                        package_name=package,
                        module_path=module,
                        symbol=module.rsplit("/", 1)[-1],
                        fully_qualified_name=module,
                        usage_kind=UsageKind.IMPORT.value,
                        file_path=rel,
                        line=line_no,
                        column=max(0, column),
                        end_line=line_no,
                        end_column=max(0, column) + len(module),
                        code_snippet=original.rstrip()[:500],
                        context={
                            "parser": "deterministic_import_syntax",
                            "import_style": match.group("style"),
                            "limitation": "literal_requires_only_no_load_path_or_runtime_resolution",
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
        edges: list[DependencyGraphEdge] = []
        for path in self._find_files(root, "Gemfile.lock"):
            rel = str(path.relative_to(root))
            try:
                _specs, _direct, lock_edges = self._parse_lock(path)
            except OSError:
                continue
            edges.extend(
                DependencyGraphEdge(parent, child, source=rel)
                for parent, child in lock_edges
            )
        node_names = {node.normalized_name for node in nodes}
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
    def _parse_gemfile(path: Path) -> list[ParsedDependency]:
        dependencies: list[ParsedDependency] = []
        dev_group_depth = 0
        block_depth = 0
        for raw_line in read_text_auto(path).splitlines():
            line = raw_line.split("#", 1)[0]
            group_match = re.match(r"^\s*group\s+(.+?)\s+do\s*$", line)
            if group_match:
                block_depth += 1
                groups = {
                    token.lower()
                    for token in re.findall(r":([A-Za-z_]\w*)", group_match.group(1))
                }
                if groups & {"development", "test", "dev", "spec"}:
                    dev_group_depth = block_depth
                continue
            if re.match(r"^\s*end\s*$", line) and block_depth:
                if block_depth == dev_group_depth:
                    dev_group_depth = 0
                block_depth -= 1
                continue
            match = _GEM_RE.match(line)
            if not match:
                continue
            name = match.group("name")
            constraint = match.group("constraint")
            inline_dev = bool(
                re.search(
                    r"\b(?:group|groups)\s*:\s*.*:(?:development|test|dev|spec)\b",
                    line,
                )
            )
            dependencies.append(
                ParsedDependency(
                    package_name=name,
                    normalized_name=normalize_gem_name(name),
                    constraint=constraint,
                    is_direct=True,
                    is_dev=bool(dev_group_depth) or inline_dev,
                    ecosystem="RubyGems",
                )
            )
        return dependencies

    @staticmethod
    def _parse_lock(path: Path) -> tuple[dict[str, str], set[str], list[tuple[str, str]]]:
        specs: dict[str, str] = {}
        direct: set[str] = set()
        edges: list[tuple[str, str]] = []
        section = ""
        current: str | None = None
        for line in read_text_auto(path).splitlines():
            if line and not line.startswith(" "):
                section = line.strip()
                current = None
                continue
            if section == "GEM":
                spec = _LOCK_SPEC_RE.match(line)
                if spec:
                    current = normalize_gem_name(spec.group("name"))
                    specs[current] = spec.group("version").split()[0]
                    continue
                child = _LOCK_CHILD_RE.match(line)
                if child and current:
                    edges.append((current, normalize_gem_name(child.group("name"))))
            elif section == "DEPENDENCIES":
                match = re.match(r"^ {2}(?P<name>[A-Za-z0-9_.-]+)", line)
                if match:
                    direct.add(normalize_gem_name(match.group("name")))
        return specs, direct, edges

    @staticmethod
    def _walk(root: Path):
        for path in root.rglob("*"):
            if path.is_file() and not any(
                part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]
            ):
                yield path

    @staticmethod
    def _find_files(root: Path, name: str) -> list[Path]:
        return sorted(path for path in RubyAnalyzer._walk(root) if path.name == name)
