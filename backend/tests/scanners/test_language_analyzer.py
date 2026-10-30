"""LanguageAnalyzer interface + PythonAnalyzer deterministic engine tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.enums import UsageKind
from app.scanners.analyzers import get_analyzer, list_analyzers
from app.scanners.analyzers.base import LanguageAnalyzer
from app.scanners.analyzers.python import PythonAnalyzer
from app.scanners.manifest import ManifestScanner

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "python_sample_repo"


@pytest.fixture
def sample_repo() -> Path:
    assert FIXTURE_ROOT.exists(), f"missing fixture repo at {FIXTURE_ROOT}"
    return FIXTURE_ROOT


def test_analyzer_registry_lists_python_and_future_languages() -> None:
    catalog = list_analyzers()
    by_id = {row["language_id"]: row for row in catalog}
    assert by_id["python"]["status"] == "implemented"
    assert by_id["javascript"]["status"] == "implemented"
    assert get_analyzer("python") is not None
    assert get_analyzer("javascript") is not None


def test_python_analyzer_implements_language_analyzer_contract(sample_repo: Path) -> None:
    analyzer = PythonAnalyzer()
    assert isinstance(analyzer, LanguageAnalyzer)
    assert analyzer.language_id == "python"
    assert analyzer.ecosystem == "PyPI"

    detection = analyzer.detect(sample_repo)
    assert detection.language_id == "python"
    assert "pip" in detection.package_managers or "poetry" in detection.package_managers


def test_python_analyzer_parses_manifests_including_setup_py(sample_repo: Path) -> None:
    analyzer = PythonAnalyzer()
    result = analyzer.parse_dependencies(sample_repo)
    merged = {d.normalized_name: d for d in result.merged_by_name()}

    assert "fastapi" in merged
    assert merged["fastapi"].version == "0.115.2"
    assert "requests" in merged
    assert "httpx" in merged
    assert "click" in merged  # from setup.py
    assert "pytest" in merged and merged["pytest"].is_dev is True
    assert any(f.endswith("requirements.txt") for f in result.files_found)
    assert any(f.endswith("setup.py") for f in result.files_found)


def test_setup_py_parser_is_ast_based(tmp_path: Path) -> None:
    (tmp_path / "setup.py").write_text(
        'from setuptools import setup\n'
        'setup(name="x", install_requires=["urllib3==2.2.0"], '
        'extras_require={"dev": ["ruff>=0.1"]})\n',
        encoding="utf-8",
    )
    result = ManifestScanner(tmp_path).scan()
    merged = {d.normalized_name: d for d in result.merged_by_name()}
    assert merged["urllib3"].version == "2.2.0"
    assert merged["ruff"].is_dev is True


def test_python_analyzer_api_usage_and_imports(sample_repo: Path) -> None:
    analyzer = PythonAnalyzer()
    known = {"fastapi", "requests", "pydantic"}
    api = analyzer.analyze_api_usage(sample_repo, known_packages=known)
    imports = analyzer.analyze_imports(sample_repo, known_packages=known)

    fqns = {u.fully_qualified_name for u in api.usages}
    kinds = {u.usage_kind for u in api.usages}

    assert api.files_parsed >= 1
    assert "requests.get" in fqns
    assert any("FastAPI" in f for f in fqns)
    assert any("BackgroundTasks" in f or "add_task" in f for f in fqns)
    assert UsageKind.CLASS_INSTANTIATION.value in kinds or UsageKind.CALL.value in kinds or (
        UsageKind.FUNCTION_CALL.value in kinds or UsageKind.METHOD_CALL.value in kinds
    )
    assert imports
    assert all(u.usage_kind in {UsageKind.IMPORT.value, UsageKind.FROM_IMPORT.value} for u in imports)


def test_python_analyzer_builds_dependency_graph_from_lockfile(sample_repo: Path) -> None:
    analyzer = PythonAnalyzer()
    graph = analyzer.build_dependency_graph(sample_repo)

    node_names = {n.normalized_name for n in graph.nodes}
    assert "fastapi" in node_names
    assert "pydantic" in node_names
    assert "starlette" in node_names

    edge_pairs = {(e.from_package, e.to_package) for e in graph.edges}
    assert ("fastapi", "pydantic") in edge_pairs
    assert ("fastapi", "starlette") in edge_pairs

    assert "fastapi" in graph.used_packages or "requests" in graph.used_packages
    payload = graph.to_dict()
    assert payload["node_count"] == len(graph.nodes)
    assert payload["edge_count"] == len(graph.edges)


def test_python_analyzer_does_not_fabricate_unknown_packages(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "import requests\nimport totally_not_installed\n",
        encoding="utf-8",
    )
    analyzer = PythonAnalyzer()
    api = analyzer.analyze_api_usage(tmp_path, known_packages={"requests"})
    packages = {u.package_name for u in api.usages}
    assert "requests" in packages
    assert "totally_not_installed" not in packages
