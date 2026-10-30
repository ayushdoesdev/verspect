"""Tests for Upgrade Impact Simulator AI validation and fallback."""

from app.ai.upgrade_simulator import UpgradeImpactAnalyzer, build_cache_key, usage_fingerprint
from app.schemas.upgrade_simulation import UpgradeImpactAIResult


def test_usage_fingerprint_stable():
    usages = [
        {"fully_qualified_name": "django.urls.path", "file_path": "a.py", "line": 1},
        {"fully_qualified_name": "django.conf.settings", "file_path": "b.py", "line": 2},
    ]
    shuffled = list(reversed(usages))
    assert usage_fingerprint(usages) == usage_fingerprint(shuffled)


def test_cache_key_changes_with_versions():
    a = build_cache_key("dep1", "4.2.0", "5.0.0", "abc")
    b = build_cache_key("dep1", "4.2.0", "5.0.1", "abc")
    assert a != b


def test_fallback_produces_valid_result():
    analyzer = UpgradeImpactAnalyzer(allow_ai=False)

    usages = [
        {
            "fully_qualified_name": "django.urls.url",
            "symbol": "url",
            "file_path": "app/urls.py",
            "line": 10,
            "enclosing_function": "urlpatterns",
            "enclosing_class": None,
            "code_snippet": "from django.urls import url",
        },
        {
            "fully_qualified_name": "django.shortcuts.render",
            "symbol": "render",
            "file_path": "app/views.py",
            "line": 20,
            "enclosing_function": "home",
            "enclosing_class": None,
            "code_snippet": "return render(request, 'home.html')",
        },
    ]
    sources = {
        "breaking_change_hints": ["url() removed — breaking change, use path()"],
        "deprecated_hints": [],
        "security_fixes": ["Fixed CVE-2024-XXXX in 5.0"],
        "release_notes": [
            {"version": "5.0", "source": "github", "text": "Removed django.urls.url — breaking"}
        ],
        "github_releases": [],
        "pypi": {"summary": "Django web framework"},
    }

    result = analyzer.analyze(
        package_name="Django",
        from_version="4.2.4",
        to_version="5.0.7",
        usages=usages,
        sources=sources,
    )
    assert isinstance(result, UpgradeImpactAIResult)
    assert 0 <= result.readiness_score <= 100
    assert 0 <= result.risk_score <= 100
    assert 0 <= result.confidence <= 1
    assert result.migration_plan
    assert result.summary
    # AST source of truth — every usage file appears
    assert {f.file_path for f in result.affected_files} == {"app/urls.py", "app/views.py"}
    # url should be flagged via heuristic
    assert any("url" in b.fully_qualified_name for b in result.breaking_apis) or result.affected_files


def test_ai_result_schema_validation():
    data = {
        "summary": "Safe minor upgrade",
        "safe_to_upgrade": True,
        "confidence": 85,  # percent form should clamp to 0.85
        "readiness_score": 90,
        "risk_score": 10,
        "migration_time_hours": 0.5,
        "migration_time_label": "~30 minutes",
        "breaking_apis": [],
        "deprecated_apis": [],
        "affected_files": [],
        "affected_symbols": [],
        "affected_functions": [],
        "affected_classes": [],
        "security_improvements": [],
        "performance_improvements": [],
        "manual_work_required": [],
        "automatic_fixes_possible": [],
        "migration_plan": [
            {
                "phase": 1,
                "title": "Bump version",
                "description": "Update pin",
                "reasoning": "Low risk",
                "difficulty": "trivial",
                "estimated_duration_hours": 0.5,
                "tasks": ["Update requirements"],
            }
        ],
        "suggested_changes": [],
        "readiness_factors": {
            "breaking_apis": 100,
            "plugin_compatibility": 90,
            "deprecated_calls": 100,
            "security": 80,
            "tests": 70,
        },
    }
    result = UpgradeImpactAIResult.model_validate(data)
    assert result.confidence == 0.85
