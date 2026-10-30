"""Go analyzer using deterministic go.mod, go.sum, and import parsing.

Source analysis is intentionally not a Go AST. It records only syntactically
simple import declarations (single imports and import blocks). API calls,
build-tag effects, generated files, and imports assembled by tooling are not
reported.
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


_SKIP_DIRS = {".git", "vendor", "node_modules", "dist", "build"}
_IMPORT_RE = re.compile(
    r'^\s*(?:import\s+)?(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*|[._])\s+)?'
    r'(?P<quote>["`])(?P<module>[^"`]+)(?P=quote)'
)


def normalize_go_module(name: str) -> str:
    """Keep Go module paths case-sensitive while removing surrounding space."""
    return (name or "").strip()


class GoAnalyzer(LanguageAnalyzer):
    language_id = "go"
    display_name = "Go"
    ecosystem = "Go"

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

        for mod_path in self._find_files(root, "go.mod"):
            rel = str(mod_path.relative_to(root))
            result.files_found.append(rel)
            try:
                _, requirements, replacements = self._parse_go_mod(read_text_auto(mod_path))
            except OSError:
                continue
            for dep in requirements:
                replacement = replacements.get(dep.package_name)
                if replacement:
                    target, replacement_version = replacement
                    detail = f"replace => {target}"
                    if replacement_version:
                        detail += f" {replacement_version}"
                        dep.version = replacement_version
                    dep.constraint = f"{dep.constraint}; {detail}" if dep.constraint else detail
                dep.manifest_source = rel
            result.dependencies.extend(requirements)

        for sum_path in self._find_files(root, "go.sum"):
            rel = str(sum_path.relative_to(root))
            result.files_found.append(rel)
            try:
                entries = self._parse_go_sum(read_text_auto(sum_path))
            except OSError:
                continue
            direct = {
                dep.normalized_name: dep
                for dep in result.dependencies
                if dep.manifest_source.endswith("go.mod")
            }
            for name, version in entries.items():
                declared = direct.get(name)
                result.dependencies.append(
                    ParsedDependency(
                        package_name=name,
                        normalized_name=name,
                        version=version,
                        constraint=declared.constraint if declared else f"=={version}",
                        is_direct=declared.is_direct if declared else False,
                        is_dev=False,
                        manifest_source=rel,
                        ecosystem="Go",
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
        """Index imports only; this deterministic parser does not inspect API calls."""
        root = Path(repo_path)
        known = {
            normalize_go_module(name)
            for name in (
                known_packages
                or [dep.normalized_name for dep in self.parse_dependencies(root).merged_by_name()]
            )
        }
        result = ASTScanResult()
        if not root.exists():
            return result

        for path in self._walk(root):
            if path.suffix.lower() != ".go":
                continue
            try:
                text = read_text_auto(path)
            except OSError:
                result.files_failed += 1
                continue
            result.files_parsed += 1
            rel = str(path.relative_to(root))
            in_import_block = False
            in_block_comment = False
            for line_no, original_line in enumerate(text.splitlines(), start=1):
                line, in_block_comment = self._strip_comments(original_line, in_block_comment)
                stripped = line.strip()
                if not stripped:
                    continue
                if in_import_block and stripped == ")":
                    in_import_block = False
                    continue
                if re.match(r"^import\s*\(\s*$", stripped):
                    in_import_block = True
                    continue
                if not in_import_block and not re.match(r"^import\s+", stripped):
                    continue
                match = _IMPORT_RE.match(line if in_import_block else stripped)
                if not match:
                    continue
                module = match.group("module")
                package = self._module_for_import(module, known)
                if package is None:
                    continue
                alias = match.group("alias")
                column = original_line.find(module)
                result.usages.append(
                    UsageRecord(
                        package_name=package,
                        module_path=module,
                        symbol=alias or module.rsplit("/", 1)[-1],
                        fully_qualified_name=module,
                        usage_kind=UsageKind.IMPORT.value,
                        file_path=rel,
                        line=line_no,
                        column=max(0, column),
                        end_line=line_no,
                        end_column=max(0, column) + len(module),
                        code_snippet=original_line.rstrip()[:500],
                        alias=alias,
                        context={
                            "parser": "deterministic_import_syntax",
                            "limitation": "imports_only_no_go_ast_or_api_calls",
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
                is_dev=False,
                manifest_source=dep.manifest_source,
            )
            for dep in merged
        ]
        node_names = {node.normalized_name for node in nodes}
        edges: list[DependencyGraphEdge] = []

        for mod_path in self._find_files(root, "go.mod"):
            rel = str(mod_path.relative_to(root))
            try:
                module_name, requirements, _ = self._parse_go_mod(read_text_auto(mod_path))
            except OSError:
                continue
            if not module_name:
                continue
            if module_name not in node_names:
                nodes.append(
                    DependencyGraphNode(
                        package_name=module_name,
                        normalized_name=module_name,
                        is_direct=True,
                        manifest_source=rel,
                    )
                )
                node_names.add(module_name)
            for dep in requirements:
                edges.append(
                    DependencyGraphEdge(
                        from_package=module_name,
                        to_package=dep.normalized_name,
                        source=rel,
                    )
                )

        usages = self.analyze_api_usage(
            root, known_packages=known_packages or sorted(node_names)
        )
        unique_edges = {
            (edge.from_package, edge.to_package, edge.source): edge for edge in edges
        }
        return DependencyGraph(
            nodes=nodes,
            edges=list(unique_edges.values()),
            used_packages=sorted({usage.package_name for usage in usages.usages}),
        )

    @staticmethod
    def _parse_go_mod(
        text: str,
    ) -> tuple[str | None, list[ParsedDependency], dict[str, tuple[str, str | None]]]:
        module_name: str | None = None
        requirements: list[ParsedDependency] = []
        replacements: dict[str, tuple[str, str | None]] = {}
        block: str | None = None

        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("module "):
                module_name = stripped.split(None, 1)[1].strip()
                continue
            if stripped in {"require (", "replace ("}:
                block = stripped.split()[0]
                continue
            if stripped == ")":
                block = None
                continue

            statement = stripped
            kind = block
            if block is None and stripped.startswith(("require ", "replace ")):
                kind, statement = stripped.split(None, 1)
            if kind == "require":
                indirect = "// indirect" in statement
                clean = statement.split("//", 1)[0].strip()
                parts = clean.split()
                if len(parts) >= 2:
                    name, version = parts[:2]
                    requirements.append(
                        ParsedDependency(
                            package_name=name,
                            normalized_name=normalize_go_module(name),
                            version=version,
                            constraint=f"=={version}",
                            is_direct=not indirect,
                            is_dev=False,
                            ecosystem="Go",
                        )
                    )
            elif kind == "replace" and "=>" in statement:
                left, right = (part.strip() for part in statement.split("=>", 1))
                old = left.split()
                new = right.split()
                if old and new:
                    replacements[old[0]] = (new[0], new[1] if len(new) > 1 else None)
        return module_name, requirements, replacements

    @staticmethod
    def _parse_go_sum(text: str) -> dict[str, str]:
        versions: dict[str, list[str]] = {}
        for raw_line in text.splitlines():
            parts = raw_line.split()
            if len(parts) < 2:
                continue
            name, version = parts[:2]
            version = version.removesuffix("/go.mod")
            values = versions.setdefault(normalize_go_module(name), [])
            if version not in values:
                values.append(version)
        return {name: sorted(values)[-1] for name, values in versions.items() if values}

    @staticmethod
    def _module_for_import(module: str, known: set[str]) -> str | None:
        candidates = [
            package
            for package in known
            if module == package or module.startswith(f"{package}/")
        ]
        return max(candidates, key=len) if candidates else None

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
                continue
            if line.startswith("/*", index):
                in_block = True
                index += 2
                continue
            if line.startswith("//", index):
                break
            output.append(line[index])
            index += 1
        return "".join(output), in_block

    @staticmethod
    def _find_files(root: Path, name: str) -> list[Path]:
        return sorted(path for path in GoAnalyzer._walk(root) if path.name == name)

    @staticmethod
    def _walk(root: Path):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
                continue
            yield path
