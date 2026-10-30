"""Manifest scanner tests."""

from pathlib import Path

from app.scanners.manifest import ManifestScanner


def test_scan_requirements_txt(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "requests==2.31.0\n# comment\nfastapi>=0.110\n",
        encoding="utf-8",
    )
    result = ManifestScanner(tmp_path).scan()
    names = {d.normalized_name for d in result.merged_by_name()}
    assert "requests" in names
    assert "fastapi" in names
    assert "requirements.txt" in result.files_found


def test_scan_utf16_requirements(tmp_path: Path):
    content = "Django==4.2.4\nPillow==10.0.0\n"
    (tmp_path / "requirements.txt").write_bytes(content.encode("utf-16"))
    result = ManifestScanner(tmp_path).scan()
    names = {d.normalized_name: d for d in result.merged_by_name()}
    assert "django" in names
    assert names["django"].version == "4.2.4"
    assert "pillow" in names


def test_scan_pyproject_pep621(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "demo"
dependencies = [
  "httpx==0.27.0",
  "pydantic>=2.0",
]
[project.optional-dependencies]
dev = ["pytest>=8.0"]
""",
        encoding="utf-8",
    )
    result = ManifestScanner(tmp_path).scan()
    merged = {d.normalized_name: d for d in result.merged_by_name()}
    assert "httpx" in merged
    assert merged["httpx"].version == "0.27.0"
    assert "pytest" in merged
    assert merged["pytest"].is_dev is True


def test_scan_uv_lock(tmp_path: Path):
    (tmp_path / "uv.lock").write_text(
        """
[[package]]
name = "httpx"
version = "0.27.0"

[[package]]
name = "idna"
version = "3.7"
""",
        encoding="utf-8",
    )
    result = ManifestScanner(tmp_path).scan()
    merged = {d.normalized_name: d for d in result.merged_by_name()}
    assert merged["httpx"].version == "0.27.0"
    assert merged["idna"].is_direct is False


def test_scan_pipfile_and_lock(tmp_path: Path):
    (tmp_path / "Pipfile").write_text(
        """
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
requests = "==2.31.0"

[dev-packages]
pytest = "*"
""",
        encoding="utf-8",
    )
    (tmp_path / "Pipfile.lock").write_text(
        """
{
  "default": {
    "requests": {"version": "==2.31.0"},
    "certifi": {"version": "==2024.2.2"}
  },
  "develop": {
    "pytest": {"version": "==8.0.0"}
  }
}
""",
        encoding="utf-8",
    )
    result = ManifestScanner(tmp_path).scan()
    merged = {d.normalized_name: d for d in result.merged_by_name()}
    assert merged["requests"].version == "2.31.0"
    assert merged["certifi"].is_direct is False
    assert merged["pytest"].is_dev is True


def test_malformed_requirements_are_skipped(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "not a package line !!!\nrequests==2.31.0\n",
        encoding="utf-8",
    )
    result = ManifestScanner(tmp_path).scan()
    names = {d.normalized_name for d in result.merged_by_name()}
    assert "requests" in names
    assert all("!!!" not in (d.package_name or "") for d in result.dependencies)
