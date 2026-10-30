"""Java analyzer using deterministic Maven, Gradle, and import parsing.

Maven POMs are parsed as XML, including simple ``${property}`` substitution and
versions inherited from ``dependencyManagement`` in the same POM. Gradle support
is intentionally limited to single-line dependency declarations with literal
``group:artifact:version`` strings or literal group/name/version map arguments.
It does not evaluate variables, version catalogs, plugins, functions, or Gradle
scripts. Java source analysis recognizes import statements only; it is not a
Java AST and does not report method or class usage.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
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


_SKIP_DIRS = {".git", ".gradle", "build", "dist", "node_modules", "target", "vendor"}
_GRADLE_CONFIGURATION = (
    r"(?:api|implementation|compileOnly|runtimeOnly|annotationProcessor|"
    r"testImplementation|testCompileOnly|testRuntimeOnly|kapt|compile)"
)
_GRADLE_COORD_RE = re.compile(
    rf"^\s*{_GRADLE_CONFIGURATION}\s*(?:\(\s*)?[\"']"
    r"(?P<group>[^:'\"]+):(?P<artifact>[^:'\"]+):(?P<version>[^'\"]+)[\"']"
)
_GRADLE_MAP_RE = re.compile(
    rf"^\s*(?P<configuration>{_GRADLE_CONFIGURATION})\s*(?:\(\s*)?"
    r"group\s*(?:=|:)\s*[\"'](?P<group>[^\"']+)[\"']\s*,\s*"
    r"(?:name|module)\s*(?:=|:)\s*[\"'](?P<artifact>[^\"']+)[\"']\s*,\s*"
    r"version\s*(?:=|:)\s*[\"'](?P<version>[^\"']+)[\"']"
)
_JAVA_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<static>static\s+)?(?P<module>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\.\*)+)\s*;"
)
_PROPERTY_RE = re.compile(r"\$\{([^}]+)\}")


def normalize_maven_name(name: str) -> str:
    """Normalize a Maven ``groupId:artifactId`` coordinate."""
    return (name or "").strip().lower()


class JavaAnalyzer(LanguageAnalyzer):
    language_id = "java"
    display_name = "Java"
    ecosystem = "Maven"

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
            if path.name not in {"pom.xml", "build.gradle", "build.gradle.kts"}:
                continue
            rel = str(path.relative_to(root))
            result.files_found.append(rel)
            try:
                if path.name == "pom.xml":
                    dependencies, _project, _licenses = self._parse_pom(path)
                else:
                    dependencies = self._parse_gradle(read_text_auto(path))
            except (OSError, ET.ParseError):
                dependencies = []
            for dependency in dependencies:
                dependency.manifest_source = rel
            result.dependencies.extend(dependencies)

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
        coordinates = {
            normalize_maven_name(name)
            for name in (
                known_packages
                or [dep.normalized_name for dep in self.parse_dependencies(root).merged_by_name()]
            )
        }
        result = ASTScanResult()
        if not root.exists():
            return result

        for path in self._walk(root):
            if path.suffix.lower() != ".java":
                continue
            try:
                text = read_text_auto(path)
            except OSError:
                result.files_failed += 1
                continue
            result.files_parsed += 1
            rel = str(path.relative_to(root))
            in_block_comment = False
            for line_no, original_line in enumerate(text.splitlines(), start=1):
                line, in_block_comment = self._strip_comments(original_line, in_block_comment)
                match = _JAVA_IMPORT_RE.match(line)
                if not match:
                    continue
                module = match.group("module").removesuffix(".*")
                package = self._coordinate_for_import(module, coordinates)
                if package is None:
                    continue
                column = original_line.find(match.group("module"))
                result.usages.append(
                    UsageRecord(
                        package_name=package,
                        module_path=module,
                        symbol=module.rsplit(".", 1)[-1],
                        fully_qualified_name=module,
                        usage_kind=UsageKind.IMPORT.value,
                        file_path=rel,
                        line=line_no,
                        column=max(0, column),
                        end_line=line_no,
                        end_column=max(0, column) + len(module),
                        code_snippet=original_line.rstrip()[:500],
                        context={
                            "parser": "deterministic_import_syntax",
                            "static": bool(match.group("static")),
                            "limitation": "imports_only_no_java_ast_or_api_calls",
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

        for path in self._find_files(root, "pom.xml"):
            rel = str(path.relative_to(root))
            try:
                dependencies, project, _licenses = self._parse_pom(path)
            except (OSError, ET.ParseError):
                continue
            if not project:
                continue
            if project not in node_names:
                nodes.append(
                    DependencyGraphNode(
                        package_name=project,
                        normalized_name=project,
                        is_direct=True,
                        manifest_source=rel,
                    )
                )
                node_names.add(project)
            for dependency in dependencies:
                edges.append(
                    DependencyGraphEdge(
                        from_package=project,
                        to_package=dependency.normalized_name,
                        relationship="depends_on" if dependency.is_direct else "manages",
                        source=rel,
                    )
                )

        usages = self.analyze_api_usage(root, known_packages=known_packages or sorted(node_names))
        unique_edges = {
            (edge.from_package, edge.to_package, edge.relationship, edge.source): edge
            for edge in edges
        }
        return DependencyGraph(
            nodes=nodes,
            edges=list(unique_edges.values()),
            used_packages=sorted({usage.package_name for usage in usages.usages}),
        )

    def pom_licenses(self, repo_path: str | Path) -> dict[str, str]:
        """Return license evidence for projects/modules and explicitly licensed deps."""
        root = Path(repo_path)
        licenses: dict[str, str] = {}
        for path in self._find_files(root, "pom.xml"):
            try:
                _dependencies, project, parsed = self._parse_pom(path)
            except (OSError, ET.ParseError):
                continue
            project_licenses, dependency_licenses = parsed
            if project and project_licenses:
                licenses[project] = project_licenses[0]
            licenses.update(dependency_licenses)
        return licenses

    @classmethod
    def _parse_pom(
        cls, path: Path
    ) -> tuple[list[ParsedDependency], str | None, tuple[list[str], dict[str, str]]]:
        root = ET.fromstring(read_text_auto(path))
        properties: dict[str, str] = {}
        properties_node = cls._child(root, "properties")
        if properties_node is not None:
            for child in list(properties_node):
                properties[cls._local_name(child.tag)] = (child.text or "").strip()

        parent = cls._child(root, "parent")
        group = cls._text(root, "groupId") or (cls._text(parent, "groupId") if parent is not None else None)
        artifact = cls._text(root, "artifactId")
        version = cls._text(root, "version") or (cls._text(parent, "version") if parent is not None else None)
        if group:
            properties.setdefault("project.groupId", group)
            properties.setdefault("pom.groupId", group)
        if artifact:
            properties.setdefault("project.artifactId", artifact)
            properties.setdefault("pom.artifactId", artifact)
        if version:
            properties.setdefault("project.version", version)
            properties.setdefault("pom.version", version)
        properties = {key: cls._resolve(value, properties) for key, value in properties.items()}

        managed_versions: dict[str, str] = {}
        management = cls._child(root, "dependencyManagement")
        if management is not None:
            dependencies_node = cls._child(management, "dependencies")
            for dependency in list(dependencies_node) if dependencies_node is not None else []:
                coordinate = cls._pom_coordinate(dependency, properties)
                dep_version = cls._resolve(cls._text(dependency, "version"), properties)
                if coordinate and dep_version:
                    managed_versions[coordinate] = dep_version

        dependencies: list[ParsedDependency] = []
        if management is not None:
            managed_node = cls._child(management, "dependencies")
            dependencies.extend(
                cls._pom_dependencies(managed_node, properties, managed_versions, is_direct=False)
            )
        direct_node = cls._child(root, "dependencies")
        dependencies.extend(
            cls._pom_dependencies(direct_node, properties, managed_versions, is_direct=True)
        )

        project = (
            normalize_maven_name(f"{cls._resolve(group, properties)}:{cls._resolve(artifact, properties)}")
            if group and artifact
            else None
        )
        project_licenses = cls._license_names(cls._child(root, "licenses"))
        dependency_licenses: dict[str, str] = {}
        for container in (direct_node, cls._child(management, "dependencies") if management is not None else None):
            for dependency in list(container) if container is not None else []:
                coordinate = cls._pom_coordinate(dependency, properties)
                names = cls._license_names(cls._child(dependency, "licenses"))
                if coordinate and names:
                    dependency_licenses[coordinate] = names[0]
        return dependencies, project, (project_licenses, dependency_licenses)

    @classmethod
    def _pom_dependencies(
        cls,
        container: ET.Element | None,
        properties: dict[str, str],
        managed_versions: dict[str, str],
        *,
        is_direct: bool,
    ) -> list[ParsedDependency]:
        parsed: list[ParsedDependency] = []
        for dependency in list(container) if container is not None else []:
            coordinate = cls._pom_coordinate(dependency, properties)
            if not coordinate:
                continue
            version = cls._resolve(cls._text(dependency, "version"), properties)
            version = version or managed_versions.get(coordinate)
            scope = (cls._text(dependency, "scope") or "").strip().lower()
            optional = (cls._text(dependency, "optional") or "").strip().lower() == "true"
            parsed.append(
                ParsedDependency(
                    package_name=coordinate,
                    normalized_name=coordinate,
                    version=version,
                    constraint=f"=={version}" if version else None,
                    is_direct=is_direct,
                    is_dev=scope == "test",
                    marker="optional" if optional else (f"scope={scope}" if scope else None),
                    ecosystem="Maven",
                )
            )
        return parsed

    @staticmethod
    def _parse_gradle(text: str) -> list[ParsedDependency]:
        dependencies: list[ParsedDependency] = []
        for raw_line in text.splitlines():
            line = raw_line.split("//", 1)[0]
            match = _GRADLE_COORD_RE.match(line) or _GRADLE_MAP_RE.match(line)
            if not match:
                continue
            coordinate = normalize_maven_name(
                f"{match.group('group')}:{match.group('artifact')}"
            )
            version = match.group("version").strip()
            if "$" in version:
                continue
            configuration_match = re.match(r"^\s*(\w+)", line)
            configuration = configuration_match.group(1) if configuration_match else ""
            dependencies.append(
                ParsedDependency(
                    package_name=coordinate,
                    normalized_name=coordinate,
                    version=version,
                    constraint=f"=={version}",
                    is_direct=True,
                    is_dev=configuration.startswith("test"),
                    marker=f"gradle_configuration={configuration}",
                    ecosystem="Maven",
                )
            )
        return dependencies

    @staticmethod
    def _coordinate_for_import(module: str, coordinates: set[str]) -> str | None:
        candidates: list[tuple[int, str]] = []
        module_lower = module.lower()
        module_tokens = set(re.split(r"[._-]", module_lower))
        for coordinate in coordinates:
            if ":" not in coordinate:
                continue
            group, artifact = coordinate.split(":", 1)
            if module_lower == group or module_lower.startswith(f"{group}."):
                candidates.append((len(group) + 1000, coordinate))
                continue
            group_parts = group.split(".")
            module_parts = module_lower.split(".")
            shared_parts = 0
            for group_part, module_part in zip(group_parts, module_parts):
                if group_part != module_part:
                    break
                shared_parts += 1
            if shared_parts >= 2:
                candidates.append((shared_parts + 100, coordinate))
                continue
            artifact_tokens = {
                token for token in re.split(r"[._-]", artifact) if len(token) > 2
            }
            if artifact_tokens and artifact_tokens.issubset(module_tokens):
                candidates.append((len(artifact_tokens), coordinate))
        return max(candidates)[1] if candidates else None

    @staticmethod
    def _resolve(value: str | None, properties: dict[str, str]) -> str | None:
        if value is None:
            return None
        resolved = value.strip()
        for _ in range(5):
            updated = _PROPERTY_RE.sub(lambda match: properties.get(match.group(1), match.group(0)), resolved)
            if updated == resolved:
                break
            resolved = updated
        return resolved or None

    @classmethod
    def _pom_coordinate(
        cls, dependency: ET.Element, properties: dict[str, str]
    ) -> str | None:
        group = cls._resolve(cls._text(dependency, "groupId"), properties)
        artifact = cls._resolve(cls._text(dependency, "artifactId"), properties)
        return normalize_maven_name(f"{group}:{artifact}") if group and artifact else None

    @staticmethod
    def _license_names(container: ET.Element | None) -> list[str]:
        names: list[str] = []
        for license_node in list(container) if container is not None else []:
            name = JavaAnalyzer._text(license_node, "name")
            if name and name.strip() not in names:
                names.append(name.strip())
        return names

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _child(cls, node: ET.Element | None, name: str) -> ET.Element | None:
        if node is None:
            return None
        return next((child for child in list(node) if cls._local_name(child.tag) == name), None)

    @classmethod
    def _text(cls, node: ET.Element | None, name: str) -> str | None:
        child = cls._child(node, name)
        return (child.text or "").strip() if child is not None and child.text else None

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
        return sorted(path for path in JavaAnalyzer._walk(root) if path.name == name)
