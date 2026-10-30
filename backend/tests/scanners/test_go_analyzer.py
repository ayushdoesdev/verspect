"""Go LanguageAnalyzer tests."""

from pathlib import Path

import pytest

from app.core.enums import LanguageSupportStatus, UsageKind
from app.scanners.analyzers import get_analyzer, list_analyzers
from app.scanners.analyzers.base import LanguageAnalyzer
from app.scanners.analyzers.go import GoAnalyzer
from app.scanners.go_modules import GoModulesClient
from app.scanners.pipelines import get_pipeline, list_language_support
from app.scanners.pipelines.go import GoPipeline


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "go_sample_repo"


@pytest.fixture
def sample_repo() -> Path:
    assert FIXTURE_ROOT.exists()
    return FIXTURE_ROOT


def test_registry_and_pipeline_resolve_go(sample_repo: Path) -> None:
    analyzer = get_analyzer("go")
    assert isinstance(analyzer, GoAnalyzer)
    assert isinstance(analyzer, LanguageAnalyzer)
    assert analyzer.language_id == "go"
    assert analyzer.ecosystem == "Go"

    detection = analyzer.detect(sample_repo)
    assert detection.language_id == "go"
    assert "go modules" in detection.package_managers
    assert detection.classification.support_status == (
        LanguageSupportStatus.SUPPORTED.value
    )
    assert isinstance(get_pipeline(detection.classification), GoPipeline)

    analyzer_catalog = {row["language_id"]: row for row in list_analyzers()}
    support_catalog = {row["language_id"]: row for row in list_language_support()}
    assert analyzer_catalog["go"]["status"] == "implemented"
    assert analyzer_catalog["go"]["ecosystem"] == "Go"
    assert support_catalog["go"]["support_status"] == "supported"


def test_parse_go_mod_go_sum_and_replace(sample_repo: Path) -> None:
    result = GoAnalyzer().parse_dependencies(sample_repo)
    merged = {dep.normalized_name: dep for dep in result.merged_by_name()}

    assert result.files_found == ["go.mod", "go.sum"]
    assert merged["github.com/gin-gonic/gin"].version == "v1.10.0"
    assert merged["github.com/gin-gonic/gin"].is_direct is True
    assert merged["golang.org/x/text"].version == "v0.16.0"
    assert merged["golang.org/x/text"].is_direct is False
    assert merged["github.com/old/module"].version == "v1.3.0"
    assert "replace => github.com/new/module v1.3.0" in (
        merged["github.com/old/module"].constraint or ""
    )
    assert all(dep.ecosystem == "Go" for dep in merged.values())


def test_analyze_go_imports_only(sample_repo: Path) -> None:
    result = GoAnalyzer().analyze_api_usage(sample_repo)
    packages = [usage.package_name for usage in result.usages]

    assert result.files_parsed == 2
    assert set(packages) == {
        "github.com/gin-gonic/gin",
        "github.com/old/module",
        "golang.org/x/text",
    }
    assert "fmt" not in packages
    assert all(usage.usage_kind == UsageKind.IMPORT.value for usage in result.usages)
    assert all(
        usage.context["limitation"] == "imports_only_no_go_ast_or_api_calls"
        for usage in result.usages
    )
    aliased = next(
        usage for usage in result.usages if usage.package_name == "golang.org/x/text"
    )
    assert aliased.alias == "textlang"
    assert aliased.module_path == "golang.org/x/text/language"


def test_build_dependency_graph_from_go_mod(sample_repo: Path) -> None:
    graph = GoAnalyzer().build_dependency_graph(sample_repo)
    nodes = {node.normalized_name: node for node in graph.nodes}
    edges = {(edge.from_package, edge.to_package) for edge in graph.edges}

    assert "github.com/verspect/go-sample" in nodes
    assert nodes["github.com/gin-gonic/gin"].version == "v1.10.0"
    assert (
        "github.com/verspect/go-sample",
        "github.com/gin-gonic/gin",
    ) in edges
    assert (
        "github.com/verspect/go-sample",
        "golang.org/x/text",
    ) in edges
    assert set(graph.used_packages) == {
        "github.com/gin-gonic/gin",
        "github.com/old/module",
        "golang.org/x/text",
    }


def test_go_metadata_marks_latest_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GoModulesClient()
    monkeypatch.setattr(client, "get_latest", lambda _package: None)

    info = client.extract_version_info("example.com/module", "v1.2.3")

    assert info["latest_version"] is None
    assert info["metadata_status"] == "latest_unavailable"
    assert info["is_outdated"] is False
