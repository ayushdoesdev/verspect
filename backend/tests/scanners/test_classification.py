"""Repository classification + pipeline routing."""

from pathlib import Path

from app.core.enums import LanguageSupportStatus
from app.scanners.analyzers import get_analyzer
from app.scanners.analyzers.javascript import JavaScriptAnalyzer
from app.scanners.classification import ClassificationResult, RepositoryClassifier
from app.scanners.language_support import (
    canonicalize_support,
    language_is_analyzable,
    support_status_for_language,
)
from app.scanners.pipelines import get_pipeline, list_language_support
from app.scanners.pipelines.base import ComingSoonPipeline
from app.scanners.pipelines.javascript import JavaScriptPipeline
from app.scanners.pipelines.python import PythonPipeline


def test_classify_python_requirements(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("django==4.2.11\nrequests>=2.31\n")
    (tmp_path / "app.py").write_text("import django\n")
    result = RepositoryClassifier(tmp_path).classify()
    assert result.language_id == "python"
    assert result.language == "Python"
    assert result.support_status == LanguageSupportStatus.FULLY_SUPPORTED.value
    assert result.support_label == "Fully Supported"
    assert result.package_manager in {"pip", "poetry", "uv", "pipenv", "setuptools"}
    assert result.framework == "Django"
    assert result.is_fully_supported is True
    assert result.can_analyze is True


def test_classify_nodejs_npm_react_is_supported(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"name":"app","dependencies":{"react":"18.0.0"}}'
    )
    (tmp_path / "package-lock.json").write_text("{}")
    result = RepositoryClassifier(tmp_path).classify()
    assert result.language_id == "javascript"
    assert "JavaScript" in result.language
    assert result.support_status == LanguageSupportStatus.SUPPORTED.value
    assert result.support_label == "Supported"
    assert result.package_manager == "npm"
    assert result.framework == "React"
    assert result.is_fully_supported is False
    assert result.can_analyze is True
    assert result.support_status != LanguageSupportStatus.COMING_SOON.value


def test_classify_typescript_and_yarn(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"name":"app","devDependencies":{"typescript":"5.4.0","@types/node":"20.0.0"}}'
    )
    (tmp_path / "yarn.lock").write_text("# yarn lockfile v1\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("export const x = 1;\n")
    result = RepositoryClassifier(tmp_path).classify()
    assert result.language_id in {"javascript", "typescript"}
    assert result.package_manager == "yarn"
    assert result.support_status == LanguageSupportStatus.SUPPORTED.value
    assert result.can_analyze is True


def test_classify_pnpm_lockfile_selects_javascript(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"app","dependencies":{"next":"14.0.0"}}')
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    result = RepositoryClassifier(tmp_path).classify()
    assert result.language_id in {"javascript", "typescript"}
    assert result.package_manager == "pnpm"
    assert isinstance(get_pipeline(result), JavaScriptPipeline)
    assert get_pipeline(result).can_analyze is True


def test_classify_go_is_supported(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.22\n")
    result = RepositoryClassifier(tmp_path).classify()
    assert result.language_id == "go"
    assert result.language == "Go"
    assert result.support_status == LanguageSupportStatus.SUPPORTED.value
    assert result.package_manager == "go modules"
    assert result.can_analyze is True


def test_classify_csharp_remains_coming_soon(tmp_path: Path):
    (tmp_path / "App.csproj").write_text("<Project></Project>\n")
    result = RepositoryClassifier(tmp_path).classify()
    assert result.language_id == "csharp"
    assert result.support_status == LanguageSupportStatus.COMING_SOON.value
    assert result.can_analyze is False
    assert isinstance(get_pipeline(result), ComingSoonPipeline)


def test_pipeline_routes_by_language_id_not_stale_status():
    py = ClassificationResult(
        language="Python",
        language_id="python",
        support_status="fully_supported",
        support_label="Fully Supported",
    )
    pipeline = get_pipeline(py)
    assert isinstance(pipeline, PythonPipeline)
    assert pipeline.is_fully_supported is True
    assert pipeline.can_analyze is True

    node = ClassificationResult(
        language="Node.js",
        language_id="javascript",
        support_status="coming_soon",
        support_label="Coming Soon",
    )
    node_pipeline = get_pipeline(node)
    assert isinstance(node_pipeline, JavaScriptPipeline)
    assert node_pipeline.can_analyze is True
    assert node_pipeline.is_fully_supported is False


def test_nodejs_alias_selects_javascript_analyzer():
    analyzer = get_analyzer("nodejs")
    assert isinstance(analyzer, JavaScriptAnalyzer)
    assert language_is_analyzable("Node.js")
    assert language_is_analyzable("javascript")
    assert support_status_for_language("nodejs") == LanguageSupportStatus.SUPPORTED


def test_stale_coming_soon_javascript_is_canonicalized_to_supported():
    status, label = canonicalize_support(
        language_id="javascript",
        support_status="coming_soon",
        support_label="Coming Soon",
    )
    assert status == LanguageSupportStatus.SUPPORTED.value
    assert label == "Supported"


def test_repository_response_remaps_stale_nodejs_coming_soon():
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.schemas.repository import RepositoryResponse

    now = datetime.now(timezone.utc)
    resp = RepositoryResponse(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        owner_id=uuid4(),
        github_repo_id=1,
        full_name="ayushdoesdev/flow-ai-auto-scheduler",
        name="flow-ai-auto-scheduler",
        owner_login="ayushdoesdev",
        html_url="https://github.com/ayushdoesdev/flow-ai-auto-scheduler",
        clone_url="https://github.com/ayushdoesdev/flow-ai-auto-scheduler.git",
        default_branch="main",
        language="TypeScript",
        detected_language="Node.js",
        detected_language_id="javascript",
        detected_framework="React",
        package_manager="npm",
        support_status="coming_soon",
        support_label="Coming Soon",
        classification={
            "language": "Node.js",
            "language_id": "javascript",
            "support_status": "coming_soon",
            "support_label": "Coming Soon",
        },
        is_private=False,
        is_fork=False,
        stars_count=0,
        forks_count=0,
        open_issues_count=0,
        is_watching=True,
        webhook_active=False,
        sync_status="idle",
        dependency_count=0,
        outdated_count=0,
        vulnerable_count=0,
        critical_alert_count=0,
        warning_count=0,
        license_issues_count=0,
    )
    assert resp.support_status == LanguageSupportStatus.SUPPORTED.value
    assert resp.support_label == "Supported"
    assert resp.detected_language == "JavaScript / Node.js"
    assert resp.classification["support_status"] == "supported"
    assert resp.classification["language"] == "JavaScript / Node.js"


def test_language_support_catalog_distinguishes_python_depth():
    catalog = list_language_support()
    by_id = {row["language_id"]: row for row in catalog}
    assert by_id["python"]["support_status"] == "fully_supported"
    assert by_id["javascript"]["support_status"] == "supported"
    assert by_id["typescript"]["support_status"] == "supported"
    assert by_id["go"]["support_status"] == "supported"
    assert by_id["javascript"]["support_label"] == "Supported"
    assert by_id["python"]["support_label"] == "Fully Supported"
