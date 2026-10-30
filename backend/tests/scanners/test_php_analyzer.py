"""PHP LanguageAnalyzer tests."""

from pathlib import Path

from app.core.enums import LanguageSupportStatus
from app.scanners.analyzers import get_analyzer, list_analyzers
from app.scanners.analyzers.php import PHPAnalyzer
from app.scanners.pipelines import get_pipeline, list_language_support
from app.scanners.pipelines.php import PHPPipeline


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "php_sample_repo"


def test_php_registry_detection_and_pipeline() -> None:
    analyzer = get_analyzer("php")
    assert isinstance(analyzer, PHPAnalyzer)
    assert analyzer.ecosystem == "Packagist"
    detection = analyzer.detect(FIXTURE_ROOT)
    assert detection.language_id == "php"
    assert "composer" in detection.package_managers
    assert detection.classification.support_status == LanguageSupportStatus.SUPPORTED.value
    assert isinstance(get_pipeline(detection.classification), PHPPipeline)
    assert {row["language_id"]: row for row in list_analyzers()}["php"]["status"] == "implemented"
    assert {row["language_id"]: row for row in list_language_support()}["php"][
        "support_status"
    ] == "supported"


def test_php_composer_dependencies_usage_and_graph() -> None:
    analyzer = PHPAnalyzer()
    result = analyzer.parse_dependencies(FIXTURE_ROOT)
    merged = {dep.normalized_name: dep for dep in result.merged_by_name()}
    assert result.files_found == ["composer.json", "composer.lock"]
    assert merged["monolog/monolog"].version == "3.7.0"
    assert merged["monolog/monolog"].is_direct is True
    assert merged["psr/log"].is_direct is False
    assert merged["phpunit/phpunit"].is_dev is True
    assert all(dep.ecosystem == "Packagist" for dep in merged.values())

    usage = analyzer.analyze_api_usage(FIXTURE_ROOT)
    assert usage.files_parsed == 1
    assert {item.package_name for item in usage.usages} == {
        "monolog/monolog",
        "guzzlehttp/guzzle",
    }
    assert all(
        item.context["limitation"] == "literal_vendor_paths_and_unambiguous_namespaces_only"
        for item in usage.usages
    )

    graph = analyzer.build_dependency_graph(FIXTURE_ROOT)
    edges = {(edge.from_package, edge.to_package) for edge in graph.edges}
    assert ("verspect/php-sample", "monolog/monolog") in edges
    assert ("monolog/monolog", "psr/log") in edges
    assert set(graph.used_packages) == {"monolog/monolog", "guzzlehttp/guzzle"}
