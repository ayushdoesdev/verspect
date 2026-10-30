"""License and health scoring tests."""

from app.scanners.health import HealthScorer, compute_release_frequency_days
from app.scanners.license import detect_license, evaluate_license_policy


def test_detect_mit():
    assert detect_license("MIT License") == "MIT"
    assert detect_license(None, "License :: OSI Approved :: MIT License") == "MIT"


def test_detect_gpl():
    assert detect_license("GPL-3.0") == "GPL-3.0"
    assert detect_license("GNU General Public License v3") == "GPL-3.0"


def test_policy_rejects_gpl():
    assert evaluate_license_policy("GPL-3.0") == "reject"
    assert evaluate_license_policy("MIT") == "allow"
    assert evaluate_license_policy("LGPL-3.0") == "warn"


def test_health_score_range():
    scorer = HealthScorer()
    result = scorer.score(
        {
            "last_release_at": None,
            "github_stars": 5000,
            "download_count_month": 200000,
            "open_issues": 10,
            "vulnerability_count": 0,
            "critical_vuln_count": 0,
        }
    )
    assert result["health_score"] is not None
    assert 0 <= result["health_score"] <= 100
    assert result["data_quality"] == "partial"
    assert "release_recency" in result["missing_signals"]
    assert "stars" in result["components"]
    assert "security" in result["components"]


def test_health_does_not_invent_missing_signals():
    scorer = HealthScorer()
    result = scorer.score({"vulnerability_count": 0, "critical_vuln_count": 0})
    assert result["data_quality"] == "partial"
    assert result["components"] == {"security": 100.0}
    assert result["health_score"] == 100.0
    assert "stars" in result["missing_signals"]
    assert "downloads" in result["missing_signals"]


def test_health_unknown_without_signals():
    scorer = HealthScorer()
    result = scorer.score({})
    assert result["health_score"] is None
    assert result["data_quality"] == "unknown"
    assert result["completeness"] == 0


def test_health_omits_security_when_osv_unavailable():
    scorer = HealthScorer()
    result = scorer.score({"github_stars": 100})
    assert "security" in result["missing_signals"]
    assert "security" not in result["components"]


def test_release_frequency_from_dates():
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    freq = compute_release_frequency_days(
        [
            {"released_at": now},
            {"released_at": now - timedelta(days=30)},
            {"released_at": now - timedelta(days=60)},
        ]
    )
    assert freq == 30.0
