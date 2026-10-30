"""JavaScript/TypeScript LanguageAnalyzer tests."""

from pathlib import Path

import pytest

from app.core.enums import UsageKind
from app.scanners.analyzers import get_analyzer
from app.scanners.analyzers.base import LanguageAnalyzer
from app.scanners.analyzers.javascript import JavaScriptAnalyzer


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "js_sample_repo"


@pytest.fixture
def sample_repo() -> Path:
    assert FIXTURE_ROOT.exists()
    return FIXTURE_ROOT


def test_registry_resolves_javascript_and_typescript() -> None:
    javascript = get_analyzer("javascript")
    typescript = get_analyzer("typescript")
    nodejs = get_analyzer("nodejs")
    assert isinstance(javascript, JavaScriptAnalyzer)
    assert isinstance(typescript, JavaScriptAnalyzer)
    assert isinstance(nodejs, JavaScriptAnalyzer)
    assert isinstance(javascript, LanguageAnalyzer)
    assert javascript.ecosystem == "npm"


def test_javascript_detection_is_supported_not_planned(sample_repo: Path) -> None:
    detection = JavaScriptAnalyzer().detect(sample_repo)
    assert detection.language_id in {"javascript", "typescript"}
    assert detection.classification.support_status == "supported"
    assert detection.classification.can_analyze is True
    assert "npm" in detection.package_managers or detection.classification.package_manager == "npm"


def test_parse_package_json_dependencies(sample_repo: Path) -> None:
    result = JavaScriptAnalyzer().parse_dependencies(sample_repo)
    package_json = [
        dep for dep in result.dependencies if dep.manifest_source == "package.json"
    ]
    by_name = {dep.normalized_name: dep for dep in package_json}

    assert by_name["express"].constraint == "^4.18.2"
    assert by_name["@scope/widget"].ecosystem == "npm"
    assert by_name["typescript"].is_dev is True
    assert all(dep.is_direct for dep in package_json)


def test_package_lock_supplies_resolved_versions(sample_repo: Path) -> None:
    result = JavaScriptAnalyzer().parse_dependencies(sample_repo)
    merged = {dep.normalized_name: dep for dep in result.merged_by_name()}

    assert merged["express"].version == "4.18.3"
    assert merged["@scope/widget"].version == "2.1.0"
    assert merged["body-parser"].version == "1.20.2"
    assert merged["body-parser"].is_direct is False
    assert merged["typescript"].is_dev is True


def test_detects_reliable_import_require_and_dynamic_import_sites(
    sample_repo: Path,
) -> None:
    result = JavaScriptAnalyzer().analyze_api_usage(sample_repo)
    packages = [usage.package_name for usage in result.usages]
    styles = {usage.context["import_style"] for usage in result.usages}

    assert result.files_parsed == 2
    assert packages.count("express") == 2
    assert packages.count("@scope/widget") == 2
    assert {"static_import", "require", "dynamic_import"} <= styles
    assert all(
        usage.usage_kind in {UsageKind.IMPORT.value, UsageKind.FROM_IMPORT.value}
        for usage in result.usages
    )


def test_builds_dependency_graph_from_package_lock(sample_repo: Path) -> None:
    graph = JavaScriptAnalyzer().build_dependency_graph(sample_repo)
    nodes = {node.normalized_name: node for node in graph.nodes}
    edges = {(edge.from_package, edge.to_package) for edge in graph.edges}

    assert nodes["express"].version == "4.18.3"
    assert "body-parser" in nodes
    assert ("express", "body-parser") in edges
    assert ("@scope/widget", "kleur") in edges
    assert set(graph.used_packages) == {"@scope/widget", "express"}


def test_pnpm_lockfile_supplies_transitive_packages(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"demo","dependencies":{"express":"^4.18.2"}}',
        encoding="utf-8",
    )
    (tmp_path / "pnpm-lock.yaml").write_text(
        """
lockfileVersion: '9.0'
packages:
  express@4.18.3:
    dependencies:
      body-parser: 1.20.2
  body-parser@1.20.2: {}
snapshots:
  express@4.18.3:
    dependencies:
      body-parser: 1.20.2
  body-parser@1.20.2: {}
""",
        encoding="utf-8",
    )
    analyzer = JavaScriptAnalyzer()
    merged = {dep.normalized_name: dep for dep in analyzer.parse_dependencies(tmp_path).merged_by_name()}
    assert merged["express"].version == "4.18.3"
    assert merged["body-parser"].version == "1.20.2"
    assert merged["body-parser"].is_direct is False
    graph = analyzer.build_dependency_graph(tmp_path)
    edges = {(edge.from_package, edge.to_package) for edge in graph.edges}
    assert ("express", "body-parser") in edges


def test_malformed_pnpm_lockfile_does_not_invent_packages(tmp_path: Path) -> None:
    (tmp_path / "pnpm-lock.yaml").write_text("this is not: [valid\n", encoding="utf-8")
    result = JavaScriptAnalyzer().parse_dependencies(tmp_path)
    assert result.dependencies == []
