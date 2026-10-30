"""JavaScript/TypeScript analyzer using deterministic manifest and source parsing.

Source analysis intentionally uses conservative regular expressions rather than
a JavaScript/TypeScript AST. It reports only single-line static imports,
``require("...")`` calls, and dynamic ``import("...")`` calls with string
literals. It does not attempt to resolve aliases, computed imports, or API calls.
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


_MANIFEST_NAMES = {"package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
_SOURCE_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
_SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".cache",
    "vendor",
}
_STATIC_IMPORT_RE = re.compile(
    r"""^\s*import\s+(?:(?P<clause>.+?)\s+from\s+)?["'](?P<module>[^"']+)["']\s*;?"""
)
_REQUIRE_RE = re.compile(r"""\brequire\s*\(\s*["'](?P<module>[^"']+)["']\s*\)""")
_DYNAMIC_IMPORT_RE = re.compile(r"""\bimport\s*\(\s*["'](?P<module>[^"']+)["']\s*\)""")


def normalize_npm_name(name: str) -> str:
    """Normalize an npm package name while preserving its scope separator."""
    return (name or "").strip().lower()


def package_root(specifier: str) -> Optional[str]:
    """Return the npm package represented by a module specifier."""
    value = specifier.strip()
    if not value or value.startswith((".", "/", "#")):
        return None
    if value.startswith("@"):
        parts = value.split("/")
        return normalize_npm_name("/".join(parts[:2])) if len(parts) >= 2 else None
    return normalize_npm_name(value.split("/", 1)[0])


class JavaScriptAnalyzer(LanguageAnalyzer):
    language_id = "javascript"
    display_name = "JavaScript / TypeScript"
    ecosystem = "npm"

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

        for path in self._walk(root):
            if path.name not in _MANIFEST_NAMES:
                continue
            rel = str(path.relative_to(root))
            result.files_found.append(rel)
            try:
                if path.name == "package.json":
                    deps = self._parse_package_json(path)
                elif path.name == "package-lock.json":
                    deps = self._parse_package_lock(path)
                elif path.name == "yarn.lock":
                    deps = self._parse_yarn_lock(path)
                elif path.name == "pnpm-lock.yaml":
                    deps = self._parse_pnpm_lock(path)
                else:
                    deps = []
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                deps = []
            for dep in deps:
                dep.manifest_source = rel
            result.dependencies.extend(deps)
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
        known = {normalize_npm_name(name) for name in (known_packages or [])}
        if not known:
            known = {d.normalized_name for d in self.parse_dependencies(root).merged_by_name()}
        result = ASTScanResult()
        if not root.exists():
            return result

        for path in self._walk(root):
            if path.suffix.lower() not in _SOURCE_SUFFIXES:
                continue
            try:
                text = read_text_auto(path)
            except OSError:
                result.files_failed += 1
                continue
            result.files_parsed += 1
            rel = str(path.relative_to(root))
            for line_no, line in enumerate(text.splitlines(), start=1):
                static = _STATIC_IMPORT_RE.search(line)
                if static:
                    self._append_usage(
                        result,
                        static.group("module"),
                        rel,
                        line_no,
                        static.start("module"),
                        line,
                        UsageKind.FROM_IMPORT.value if static.group("clause") else UsageKind.IMPORT.value,
                        static.group("clause"),
                        known,
                        "static_import",
                    )
                    continue
                for pattern, source in (
                    (_REQUIRE_RE, "require"),
                    (_DYNAMIC_IMPORT_RE, "dynamic_import"),
                ):
                    for match in pattern.finditer(line):
                        self._append_usage(
                            result,
                            match.group("module"),
                            rel,
                            line_no,
                            match.start("module"),
                            line,
                            UsageKind.IMPORT.value,
                            None,
                            known,
                            source,
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
                package_name=d.package_name,
                normalized_name=d.normalized_name,
                version=d.version,
                is_direct=d.is_direct,
                is_dev=d.is_dev,
                manifest_source=d.manifest_source,
            )
            for d in merged
        ]
        edges: list[DependencyGraphEdge] = []
        for path in self._walk(root):
            if path.name == "package-lock.json":
                try:
                    edges.extend(
                        self._package_lock_edges(path, str(path.relative_to(root)))
                    )
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
            elif path.name == "yarn.lock":
                try:
                    edges.extend(self._yarn_lock_edges(path, str(path.relative_to(root))))
                except OSError:
                    continue
            elif path.name == "pnpm-lock.yaml":
                try:
                    edges.extend(self._pnpm_lock_edges(path, str(path.relative_to(root))))
                except OSError:
                    continue

        node_names = {node.normalized_name for node in nodes}
        versions = {d.normalized_name: d.version for d in merged}
        for edge in edges:
            for name in (edge.from_package, edge.to_package):
                if name not in node_names:
                    nodes.append(
                        DependencyGraphNode(
                            package_name=name,
                            normalized_name=name,
                            version=versions.get(name),
                            is_direct=False,
                            manifest_source=edge.source,
                        )
                    )
                    node_names.add(name)

        usages = self.analyze_api_usage(
            root, known_packages=known_packages or list(node_names)
        )
        used = sorted({normalize_npm_name(item.package_name) for item in usages.usages})
        unique_edges = {
            (edge.from_package, edge.to_package, edge.source): edge for edge in edges
        }
        return DependencyGraph(nodes=nodes, edges=list(unique_edges.values()), used_packages=used)

    @staticmethod
    def _walk(root: Path):
        for path in root.rglob("*"):
            if path.is_file() and not any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
                yield path

    @staticmethod
    def _parse_package_json(path: Path) -> list[ParsedDependency]:
        data = json.loads(read_text_auto(path))
        deps: list[ParsedDependency] = []
        for section, is_dev in (("dependencies", False), ("devDependencies", True)):
            block = data.get(section) or {}
            if not isinstance(block, dict):
                continue
            for name, constraint in block.items():
                deps.append(
                    ParsedDependency(
                        package_name=str(name),
                        normalized_name=normalize_npm_name(str(name)),
                        constraint=str(constraint) if constraint is not None else None,
                        is_dev=is_dev,
                        is_direct=True,
                        ecosystem="npm",
                    )
                )
        return deps

    @classmethod
    def _parse_package_lock(cls, path: Path) -> list[ParsedDependency]:
        data = json.loads(read_text_auto(path))
        direct, dev = cls._root_dependency_sets(data)
        deps: list[ParsedDependency] = []
        packages = data.get("packages")
        if isinstance(packages, dict):  # lockfileVersion 2/3
            for key, metadata in packages.items():
                if not key or not isinstance(metadata, dict):
                    continue
                name = metadata.get("name") or cls._name_from_lock_path(str(key))
                if not name:
                    continue
                normalized = normalize_npm_name(str(name))
                version = metadata.get("version")
                deps.append(
                    ParsedDependency(
                        package_name=str(name),
                        normalized_name=normalized,
                        version=str(version) if version is not None else None,
                        constraint=f"=={version}" if version is not None else None,
                        is_dev=bool(metadata.get("dev")) or normalized in dev,
                        is_direct=normalized in direct,
                        ecosystem="npm",
                    )
                )
        else:  # lockfileVersion 1
            def visit(block: dict[str, Any], top_level: bool = False) -> None:
                for name, metadata in block.items():
                    if not isinstance(metadata, dict):
                        continue
                    normalized = normalize_npm_name(str(name))
                    version = metadata.get("version")
                    deps.append(
                        ParsedDependency(
                            package_name=str(name),
                            normalized_name=normalized,
                            version=str(version) if version is not None else None,
                            constraint=f"=={version}" if version is not None else None,
                            is_dev=bool(metadata.get("dev")) or normalized in dev,
                            is_direct=top_level or normalized in direct,
                            ecosystem="npm",
                        )
                    )
                    nested = metadata.get("dependencies")
                    if isinstance(nested, dict):
                        visit(nested)

            if isinstance(data.get("dependencies"), dict):
                visit(data["dependencies"], top_level=True)
        return deps

    @staticmethod
    def _root_dependency_sets(data: dict[str, Any]) -> tuple[set[str], set[str]]:
        root = (data.get("packages") or {}).get("", {}) if isinstance(data.get("packages"), dict) else {}
        prod = root.get("dependencies") if isinstance(root, dict) else None
        dev_block = root.get("devDependencies") if isinstance(root, dict) else None
        if not isinstance(prod, dict):
            prod = data.get("dependencies") if isinstance(data.get("dependencies"), dict) else {}
        if not isinstance(dev_block, dict):
            dev_block = data.get("devDependencies") if isinstance(data.get("devDependencies"), dict) else {}
        dev = {normalize_npm_name(str(name)) for name in dev_block}
        return ({normalize_npm_name(str(name)) for name in prod} | dev, dev)

    @staticmethod
    def _name_from_lock_path(value: str) -> Optional[str]:
        marker = "node_modules/"
        if marker not in value:
            return None
        return value.rsplit(marker, 1)[-1] or None

    @classmethod
    def _package_lock_edges(cls, path: Path, source: str) -> list[DependencyGraphEdge]:
        data = json.loads(read_text_auto(path))
        edges: list[DependencyGraphEdge] = []
        packages = data.get("packages")
        if isinstance(packages, dict):
            for key, metadata in packages.items():
                if not key or not isinstance(metadata, dict):
                    continue
                parent = metadata.get("name") or cls._name_from_lock_path(str(key))
                if not parent:
                    continue
                for child in (metadata.get("dependencies") or {}):
                    edges.append(
                        DependencyGraphEdge(
                            from_package=normalize_npm_name(str(parent)),
                            to_package=normalize_npm_name(str(child)),
                            source=source,
                        )
                    )
        else:
            def visit(block: dict[str, Any]) -> None:
                for parent, metadata in block.items():
                    if not isinstance(metadata, dict):
                        continue
                    nested = metadata.get("dependencies") or {}
                    if isinstance(nested, dict):
                        for child in nested:
                            edges.append(
                                DependencyGraphEdge(
                                    from_package=normalize_npm_name(str(parent)),
                                    to_package=normalize_npm_name(str(child)),
                                    source=source,
                                )
                            )
                        visit(nested)

            if isinstance(data.get("dependencies"), dict):
                visit(data["dependencies"])
        return edges

    @staticmethod
    def _parse_yarn_lock(path: Path) -> list[ParsedDependency]:
        entries = JavaScriptAnalyzer._yarn_entries(read_text_auto(path))
        return [
            ParsedDependency(
                package_name=name,
                normalized_name=normalize_npm_name(name),
                version=metadata.get("version"),
                constraint=f"=={metadata['version']}" if metadata.get("version") else None,
                is_direct=False,
                ecosystem="npm",
            )
            for name, metadata in entries
        ]

    @staticmethod
    def _yarn_lock_edges(path: Path, source: str) -> list[DependencyGraphEdge]:
        edges: list[DependencyGraphEdge] = []
        for parent, metadata in JavaScriptAnalyzer._yarn_entries(read_text_auto(path)):
            for child in metadata.get("dependencies", []):
                edges.append(
                    DependencyGraphEdge(
                        from_package=normalize_npm_name(parent),
                        to_package=normalize_npm_name(child),
                        source=source,
                    )
                )
        return edges

    @staticmethod
    def _yarn_entries(text: str) -> list[tuple[str, dict[str, Any]]]:
        entries: list[tuple[str, dict[str, Any]]] = []
        current: Optional[str] = None
        metadata: dict[str, Any] = {}
        in_dependencies = False
        for line in text.splitlines():
            if line and not line.startswith((" ", "#")) and line.endswith(":"):
                if current:
                    entries.append((current, metadata))
                selector = line[:-1].split(",", 1)[0].strip().strip('"')
                if selector.startswith("@"):
                    current = selector.rsplit("@", 1)[0]
                else:
                    current = selector.split("@", 1)[0]
                metadata = {"dependencies": []}
                in_dependencies = False
            elif current and re.match(r"^\s{2}version\s+", line):
                match = re.search(r"""version\s+["']?([^"'\s]+)""", line)
                if match:
                    metadata["version"] = match.group(1)
                in_dependencies = False
            elif current and line.strip() == "dependencies:":
                in_dependencies = True
            elif current and in_dependencies and re.match(r"^\s{4}\S", line):
                child = line.strip().split()[0].strip('"')
                metadata["dependencies"].append(child)
            elif line and not line.startswith("    "):
                in_dependencies = False
        if current:
            entries.append((current, metadata))
        return entries

    @staticmethod
    def _pnpm_package_name(key: str) -> Optional[str]:
        raw = key.strip().strip("'\"").lstrip("/")
        if not raw or raw in {"packages", "snapshots", "importers", "dependencies"}:
            return None
        # Drop peer suffix: express@4.18.3(foo@1.0.0)
        if "(" in raw:
            raw = raw.split("(", 1)[0]
        if raw.startswith("@"):
            # @scope/name@version
            if raw.count("@") < 2:
                return normalize_npm_name(raw)
            return normalize_npm_name(raw.rsplit("@", 1)[0])
        if "@" not in raw:
            return normalize_npm_name(raw)
        return normalize_npm_name(raw.split("@", 1)[0])

    @staticmethod
    def _parse_pnpm_lock(path: Path) -> list[ParsedDependency]:
        names: dict[str, Optional[str]] = {}
        for name, version, _children in JavaScriptAnalyzer._pnpm_packages(read_text_auto(path)):
            names.setdefault(name, version)
        return [
            ParsedDependency(
                package_name=name,
                normalized_name=normalize_npm_name(name),
                version=version,
                constraint=f"=={version}" if version else None,
                is_direct=False,
                ecosystem="npm",
            )
            for name, version in names.items()
        ]

    @staticmethod
    def _pnpm_lock_edges(path: Path, source: str) -> list[DependencyGraphEdge]:
        edges: list[DependencyGraphEdge] = []
        for name, _version, children in JavaScriptAnalyzer._pnpm_packages(read_text_auto(path)):
            for child in children:
                edges.append(
                    DependencyGraphEdge(
                        from_package=normalize_npm_name(name),
                        to_package=normalize_npm_name(child),
                        source=source,
                    )
                )
        return edges

    @staticmethod
    def _pnpm_packages(text: str) -> list[tuple[str, Optional[str], list[str]]]:
        """Parse pnpm-lock.yaml packages/snapshots without a YAML library.

        Supports lockfileVersion 6 (`/express@4.18.3:`) and 9 (`express@4.18.3:`).
        Malformed input yields no invented packages.
        """
        packages: list[tuple[str, Optional[str], list[str]]] = []
        in_packages = False
        current: Optional[str] = None
        version: Optional[str] = None
        children: list[str] = []
        in_deps = False

        def flush() -> None:
            nonlocal current, version, children, in_deps
            if current:
                packages.append((current, version, children))
            current = None
            version = None
            children = []
            in_deps = False

        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if re.match(r"^(packages|snapshots):\s*$", line):
                flush()
                in_packages = True
                continue
            if in_packages and re.match(r"^[A-Za-z]", line) and line.rstrip().endswith(":"):
                # Next top-level mapping (importers, settings, …)
                flush()
                in_packages = False
                continue
            if not in_packages:
                continue
            key_match = re.match(
                r"^ {2}('([^']+)'|\"([^\"]+)\"|([^:\s]+)):\s*(\{\}\s*)?$",
                line,
            )
            if key_match:
                flush()
                raw_key = key_match.group(2) or key_match.group(3) or key_match.group(4)
                current = JavaScriptAnalyzer._pnpm_package_name(raw_key)
                stripped = (raw_key or "").strip().strip("'\"").lstrip("/")
                if "(" in stripped:
                    stripped = stripped.split("(", 1)[0]
                if stripped.startswith("@") and stripped.count("@") >= 2:
                    version = stripped.rsplit("@", 1)[1]
                elif not stripped.startswith("@") and "@" in stripped:
                    version = stripped.split("@", 1)[1]
                continue
            if current is None:
                continue
            ver_match = re.match(r"^\s{4}version:\s*['\"]?([^'\"\s]+)", line)
            if ver_match:
                version = ver_match.group(1)
                in_deps = False
                continue
            if re.match(r"^\s{4}dependencies:\s*$", line):
                in_deps = True
                continue
            if in_deps and re.match(r"^\s{6}\S", line):
                child_raw = line.strip().split(":", 1)[0].strip().strip("'\"")
                child = JavaScriptAnalyzer._pnpm_package_name(
                    child_raw if "@" in child_raw else f"{child_raw}@0"
                )
                # child keys in v6/v9 deps are often `body-parser: 1.20.2` (name only)
                if "@" not in child_raw and not child_raw.startswith("/"):
                    child = normalize_npm_name(child_raw)
                if child:
                    children.append(child)
                continue
            if line.startswith("    ") and not line.startswith("      "):
                in_deps = False
        flush()
        return [(name, ver, kids) for name, ver, kids in packages if name]

    @staticmethod
    def _append_usage(
        result: ASTScanResult,
        module: str,
        file_path: str,
        line_no: int,
        column: int,
        line: str,
        kind: str,
        symbol: Optional[str],
        known: set[str],
        source: str,
    ) -> None:
        package = package_root(module)
        if package is None or (known and package not in known):
            return
        cleaned_symbol = (symbol or package).strip()[:250]
        result.usages.append(
            UsageRecord(
                package_name=package,
                module_path=module,
                symbol=cleaned_symbol,
                fully_qualified_name=module,
                usage_kind=kind,
                file_path=file_path,
                line=line_no,
                column=column,
                end_line=line_no,
                end_column=column + len(module),
                code_snippet=line.rstrip()[:500],
                context={"parser": "regex", "import_style": source},
            )
        )
