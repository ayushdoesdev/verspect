"""Rust LanguageAnalyzer tests."""

from pathlib import Path

from app.core.enums import LanguageSupportStatus, UsageKind
from app.scanners.analyzers import get_analyzer, list_analyzers
from app.scanners.analyzers.rust import RustAnalyzer
from app.scanners.pipelines import get_pipeline, list_language_support
from app.scanners.pipelines.rust import RustPipeline


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "rust_sample_repo"


def test_rust_registry_detection_and_pipeline() -> None:
    analyzer = get_analyzer("rust")
    assert isinstance(analyzer, RustAnalyzer)
    assert analyzer.ecosystem == "crates.io"
    detection = analyzer.detect(FIXTURE_ROOT)
    assert detection.language_id == "rust"
    assert "cargo" in detection.package_managers
    assert detection.classification.support_status == LanguageSupportStatus.SUPPORTED.value
    assert isinstance(get_pipeline(detection.classification), RustPipeline)
    assert {row["language_id"]: row for row in list_analyzers()}["rust"]["status"] == "implemented"
    assert {row["language_id"]: row for row in list_language_support()}["rust"][
        "support_status"
    ] == "supported"


def test_rust_cargo_dependencies_imports_and_graph() -> None:
    analyzer = RustAnalyzer()
    result = analyzer.parse_dependencies(FIXTURE_ROOT)
    merged = {dep.normalized_name: dep for dep in result.merged_by_name()}
    assert result.files_found == ["Cargo.lock", "Cargo.toml"]
    assert merged["serde"].version == "1.0.204"
    assert merged["serde"].is_direct is True
    assert merged["pin-project-lite"].is_direct is False
    assert merged["rand"].version == "0.8.5"
    assert merged["pretty-assertions"].is_dev is True
    assert "verspect-rust-sample" not in merged
    assert all(dep.ecosystem == "crates.io" for dep in merged.values())

    usage = analyzer.analyze_api_usage(FIXTURE_ROOT)
    assert usage.files_parsed == 1
    assert {item.package_name for item in usage.usages} == {"serde", "tokio", "rand"}
    assert all(item.usage_kind == UsageKind.IMPORT.value for item in usage.usages)
    assert all("simple_imports_only" in item.context["limitation"] for item in usage.usages)

    graph = analyzer.build_dependency_graph(FIXTURE_ROOT)
    edges = {(edge.from_package, edge.to_package) for edge in graph.edges}
    assert ("verspect-rust-sample", "serde") in edges
    assert ("tokio", "pin-project-lite") in edges
    assert set(graph.used_packages) == {"serde", "tokio", "rand"}
