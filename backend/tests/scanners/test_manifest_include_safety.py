"""Requirements include safety regression tests."""

from pathlib import Path

from app.scanners.manifest import ManifestScanner


def test_requirements_include_cycle_is_processed_once(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "-r requirements-dev.txt\nrequests==2.32.0\n", encoding="utf-8"
    )
    (tmp_path / "requirements-dev.txt").write_text(
        "--requirement requirements.txt\npytest==8.3.0\n", encoding="utf-8"
    )

    result = ManifestScanner(tmp_path).scan()
    versions = {dep.normalized_name: dep.version for dep in result.dependencies}

    assert versions["requests"] == "2.32.0"
    assert versions["pytest"] == "8.3.0"
    assert len([dep for dep in result.dependencies if dep.normalized_name == "requests"]) == 1
    assert len([dep for dep in result.dependencies if dep.normalized_name == "pytest"]) == 1


def test_requirements_include_cannot_escape_repository(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside-requirements.txt"
    outside.write_text("should-not-be-installed==1.0.0\n", encoding="utf-8")
    try:
        (tmp_path / "requirements.txt").write_text(
            f"-r ../{outside.name}\nrequests==2.32.0\n", encoding="utf-8"
        )

        result = ManifestScanner(tmp_path).scan()
        names = {dep.normalized_name for dep in result.dependencies}

        assert "requests" in names
        assert "should-not-be-installed" not in names
    finally:
        outside.unlink(missing_ok=True)


def test_requirements_include_rejects_symlink_escape(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside-link.txt"
    outside.write_text("should-not-be-installed==1.0.0\n", encoding="utf-8")
    try:
        (tmp_path / "requirements.txt").write_text(
            "-r linked-requirements.txt\nrequests==2.32.0\n", encoding="utf-8"
        )
        (tmp_path / "linked-requirements.txt").symlink_to(outside)

        result = ManifestScanner(tmp_path).scan()
        names = {dep.normalized_name for dep in result.dependencies}

        assert "requests" in names
        assert "should-not-be-installed" not in names
    finally:
        outside.unlink(missing_ok=True)
