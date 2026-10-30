"""Dependency health scoring (0–100).

Only signals that were actually observed contribute to the score. Missing
registry/GitHub metrics are listed in `missing_signals` instead of being
filled with optimistic defaults.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _days_since(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0


def compute_release_frequency_days(releases: list[dict[str, Any]]) -> Optional[float]:
    """Average days between the most recent releases. None if fewer than two dates."""
    dates: list[datetime] = []
    for row in releases:
        value = row.get("released_at") if isinstance(row, dict) else None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            dates.append(value)
    if len(dates) < 2:
        return None
    dates.sort(reverse=True)
    sample = dates[:12]
    deltas = [
        (sample[i] - sample[i + 1]).total_seconds() / 86400.0
        for i in range(len(sample) - 1)
    ]
    if not deltas:
        return None
    return round(sum(deltas) / len(deltas), 1)


class HealthScorer:
    """
    Weighted health score using observed signals only:
    - Release frequency / recency
    - GitHub stars
    - Last commit / last release
    - Downloads
    - Open issues
    - Security history
    """

    WEIGHTS = {
        "release_recency": 0.20,
        "release_frequency": 0.10,
        "stars": 0.15,
        "downloads": 0.15,
        "open_issues": 0.10,
        "security": 0.20,
        "maintenance": 0.10,
    }

    def score(self, metrics: dict[str, Any]) -> dict[str, Any]:
        components: dict[str, float] = {}
        present: set[str] = set()

        days_release = _days_since(metrics.get("last_release_at"))
        if days_release is not None:
            if days_release <= 30:
                components["release_recency"] = 100.0
            elif days_release <= 90:
                components["release_recency"] = 85.0
            elif days_release <= 180:
                components["release_recency"] = 70.0
            elif days_release <= 365:
                components["release_recency"] = 50.0
            elif days_release <= 730:
                components["release_recency"] = 30.0
            else:
                components["release_recency"] = 10.0
            present.add("release_recency")

        freq = metrics.get("release_frequency_days")
        if freq is not None:
            if freq <= 30:
                components["release_frequency"] = 100.0
            elif freq <= 60:
                components["release_frequency"] = 85.0
            elif freq <= 120:
                components["release_frequency"] = 70.0
            elif freq <= 180:
                components["release_frequency"] = 55.0
            else:
                components["release_frequency"] = 35.0
            present.add("release_frequency")

        if metrics.get("github_stars") is not None:
            stars = int(metrics.get("github_stars") or 0)
            if stars >= 10000:
                components["stars"] = 100.0
            elif stars >= 1000:
                components["stars"] = 85.0
            elif stars >= 100:
                components["stars"] = 70.0
            elif stars >= 10:
                components["stars"] = 50.0
            elif stars > 0:
                components["stars"] = 30.0
            else:
                components["stars"] = 20.0
            present.add("stars")

        if metrics.get("download_count_month") is not None:
            downloads = int(metrics.get("download_count_month") or 0)
            if downloads >= 1_000_000:
                components["downloads"] = 100.0
            elif downloads >= 100_000:
                components["downloads"] = 90.0
            elif downloads >= 10_000:
                components["downloads"] = 75.0
            elif downloads >= 1_000:
                components["downloads"] = 55.0
            elif downloads > 0:
                components["downloads"] = 35.0
            else:
                components["downloads"] = 20.0
            present.add("downloads")

        if metrics.get("open_issues") is not None:
            issues = int(metrics.get("open_issues") or 0)
            if issues == 0:
                components["open_issues"] = 70.0
            elif issues <= 20:
                components["open_issues"] = 90.0
            elif issues <= 100:
                components["open_issues"] = 70.0
            elif issues <= 500:
                components["open_issues"] = 50.0
            else:
                components["open_issues"] = 30.0
            present.add("open_issues")

        if "vulnerability_count" in metrics or "critical_vuln_count" in metrics:
            vuln_count = int(metrics.get("vulnerability_count") or 0)
            critical = int(metrics.get("critical_vuln_count") or 0)
            if critical > 0:
                components["security"] = max(0.0, 40.0 - critical * 15)
            elif vuln_count > 0:
                components["security"] = max(20.0, 80.0 - vuln_count * 10)
            else:
                components["security"] = 100.0
            present.add("security")

        days_commit = _days_since(metrics.get("last_commit_at"))
        if days_commit is not None:
            if days_commit <= 30:
                components["maintenance"] = 100.0
            elif days_commit <= 90:
                components["maintenance"] = 80.0
            elif days_commit <= 180:
                components["maintenance"] = 60.0
            elif days_commit <= 365:
                components["maintenance"] = 40.0
            else:
                components["maintenance"] = 15.0
            present.add("maintenance")
        elif "release_recency" in present:
            components["maintenance"] = components["release_recency"]
            present.add("maintenance")

        active_weights = {key: weight for key, weight in self.WEIGHTS.items() if key in present}
        weight_sum = sum(active_weights.values())
        if present and weight_sum > 0:
            total = 0.0
            renormalized: dict[str, float] = {}
            for key, weight in active_weights.items():
                share = weight / weight_sum
                renormalized[key] = round(share, 4)
                total += components.get(key, 50.0) * share
            final: Optional[float] = round(_clamp(total), 1)
            weights_out = renormalized
        else:
            final = None
            weights_out = {}

        missing = [key for key in self.WEIGHTS if key not in present]
        if not present:
            data_quality = "unknown"
        elif missing:
            data_quality = "partial"
        else:
            data_quality = "complete"

        return {
            "health_score": final,
            "components": components,
            "weights": weights_out,
            "missing_signals": missing,
            "completeness": round(len(present) / len(self.WEIGHTS), 2),
            "data_quality": data_quality,
        }

    def risk_score(
        self,
        health_score: Optional[float],
        is_outdated: bool,
        major_behind: int,
        vulnerability_count: int,
        license_action: Optional[str],
    ) -> float:
        risk = 50.0 if health_score is None else 100.0 - health_score
        if is_outdated:
            risk += 5 + major_behind * 8
        risk += vulnerability_count * 10
        if license_action == "reject":
            risk += 25
        elif license_action == "warn":
            risk += 10
        return round(_clamp(risk), 1)
