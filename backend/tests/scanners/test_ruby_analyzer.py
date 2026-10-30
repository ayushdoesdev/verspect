"""Ruby LanguageAnalyzer tests."""

from pathlib import Path

from app.core.enums import LanguageSupportStatus
from app.scanners.analyzers import get_analyzer, list_analyzers
from app.scanners.analyzers.ruby import RubyAnalyzer
from app.scanners.pipelines import get_pipeline, list_language_support
from app.scanners.pipelines.ruby import RubyPipeline


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ruby_sample_repo"


def test_ruby_registry_detection_and_pipeline() -> None:
    analyzer = get_analyzer("ruby")
    assert isinstance(analyzer, RubyAnalyzer)
    assert analyzer.ecosystem == "RubyGems"
    detection = analyzer.detect(FIXTURE_ROOT)
    assert detection.language_id == "ruby"
    assert "bundler" in detection.package_managers
    assert detection.classification.support_status == LanguageSupportStatus.SUPPORTED.value
    assert isinstance(get_pipeline(detection.classification), RubyPipeline)
    assert {row["language_id"]: row for row in list_analyzers()}["ruby"]["status"] == "implemented"
    assert {row["language_id"]: row for row in list_language_support()}["ruby"][
        "support_status"
    ] == "supported"


def test_ruby_bundler_dependencies_requires_and_graph() -> None:
    analyzer = RubyAnalyzer()
    result = analyzer.parse_dependencies(FIXTURE_ROOT)
    merged = {dep.normalized_name: dep for dep in result.merged_by_name()}
    assert result.files_found == ["Gemfile", "Gemfile.lock"]
    assert merged["rack"].version == "3.1.7"
    assert merged["rack"].is_direct is True
    assert merged["mini_mime"].is_direct is False
    assert merged["rspec"].is_dev is True
    assert all(dep.ecosystem == "RubyGems" for dep in merged.values())

    usage = analyzer.analyze_api_usage(FIXTURE_ROOT)
    assert usage.files_parsed == 1
    assert [item.package_name for item in usage.usages] == ["rack", "httparty", "rack"]
    assert {item.context["import_style"] for item in usage.usages} == {
        "require",
        "require_relative",
    }
    assert all("literal_requires_only" in item.context["limitation"] for item in usage.usages)

    graph = analyzer.build_dependency_graph(FIXTURE_ROOT)
    assert ("httparty", "mini_mime") in {
        (edge.from_package, edge.to_package) for edge in graph.edges
    }
    assert set(graph.used_packages) == {"rack", "httparty"}
