"""Java LanguageAnalyzer tests."""

from pathlib import Path

import pytest

from app.core.enums import LanguageSupportStatus, UsageKind
from app.scanners.analyzers import get_analyzer, list_analyzers
from app.scanners.analyzers.base import LanguageAnalyzer
from app.scanners.analyzers.java import JavaAnalyzer
from app.scanners.pipelines import get_pipeline, list_language_support
from app.scanners.pipelines.java import JavaPipeline


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "java_sample_repo"


@pytest.fixture
def sample_repo() -> Path:
    assert FIXTURE_ROOT.exists()
    return FIXTURE_ROOT


def test_registry_and_pipeline_resolve_java(sample_repo: Path) -> None:
    analyzer = get_analyzer("java")
    assert isinstance(analyzer, JavaAnalyzer)
    assert isinstance(analyzer, LanguageAnalyzer)
    assert analyzer.language_id == "java"
    assert analyzer.ecosystem == "Maven"

    detection = analyzer.detect(sample_repo)
    assert detection.language_id == "java"
    assert {"maven", "gradle"}.issubset(set(detection.package_managers))
    assert detection.classification.support_status == (
        LanguageSupportStatus.SUPPORTED.value
    )
    assert isinstance(get_pipeline(detection.classification), JavaPipeline)

    analyzers = {row["language_id"]: row for row in list_analyzers()}
    support = {row["language_id"]: row for row in list_language_support()}
    assert analyzers["java"]["status"] == "implemented"
    assert analyzers["java"]["ecosystem"] == "Maven"
    assert support["java"]["support_status"] == "supported"


def test_parse_pom_and_basic_gradle_dependencies(sample_repo: Path) -> None:
    result = JavaAnalyzer().parse_dependencies(sample_repo)
    merged = {dependency.normalized_name: dependency for dependency in result.merged_by_name()}

    assert result.files_found == ["build.gradle", "build.gradle.kts", "pom.xml"]
    assert merged["com.google.guava:guava"].version == "33.2.1-jre"
    assert merged["com.google.guava:guava"].is_direct is True
    assert merged["org.apache.commons:commons-lang3"].version == "3.14.0"
    assert merged["org.apache.commons:commons-lang3"].is_dev is True
    assert merged["org.slf4j:slf4j-api"].version == "2.0.13"
    assert merged["org.junit.jupiter:junit-jupiter"].version == "5.10.2"
    assert all(dependency.ecosystem == "Maven" for dependency in merged.values())


def test_java_import_analysis_reads_java_files_only(sample_repo: Path) -> None:
    result = JavaAnalyzer().analyze_api_usage(sample_repo)

    assert result.files_parsed == 1
    assert {usage.package_name for usage in result.usages} == {
        "com.google.guava:guava",
        "org.apache.commons:commons-lang3",
        "org.slf4j:slf4j-api",
    }
    assert all(usage.usage_kind == UsageKind.IMPORT.value for usage in result.usages)
    assert all(
        usage.context["limitation"] == "imports_only_no_java_ast_or_api_calls"
        for usage in result.usages
    )
    assert "org.junit.jupiter:junit-jupiter" not in {
        usage.package_name for usage in result.usages
    }


def test_dependency_graph_uses_pom_dependencies_and_management(sample_repo: Path) -> None:
    graph = JavaAnalyzer().build_dependency_graph(sample_repo)
    nodes = {node.normalized_name: node for node in graph.nodes}
    edges = {
        (edge.from_package, edge.to_package, edge.relationship) for edge in graph.edges
    }

    assert "com.verspect:java-sample" in nodes
    assert (
        "com.verspect:java-sample",
        "com.google.guava:guava",
        "depends_on",
    ) in edges
    assert (
        "com.verspect:java-sample",
        "com.google.guava:guava",
        "manages",
    ) in edges
    assert "org.slf4j:slf4j-api" in graph.used_packages


def test_pom_license_evidence_is_coordinate_specific(sample_repo: Path) -> None:
    licenses = JavaAnalyzer().pom_licenses(sample_repo)

    assert licenses["com.verspect:java-sample"] == "Apache-2.0"
    assert licenses["org.apache.commons:commons-lang3"] == "Apache-2.0"
    assert "com.google.guava:guava" not in licenses


def test_gradle_parser_ignores_nonliteral_and_multiline_declarations() -> None:
    dependencies = JavaAnalyzer._parse_gradle(
        """
        implementation("com.example:literal:1.2.3")
        implementation("com.example:variable:$version")
        implementation(
            "com.example:multiline:2.0.0"
        )
        """
    )

    assert [dependency.package_name for dependency in dependencies] == [
        "com.example:literal",
    ]
