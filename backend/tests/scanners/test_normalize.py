"""Tests for package name normalization and requirement parsing."""

from app.scanners.normalize import normalize_package_name, parse_requirement_line


def test_normalize_package_name():
    assert normalize_package_name("PyPDF2") == "pypdf2"
    assert normalize_package_name("Django_REST_framework") == "django-rest-framework"
    assert normalize_package_name("requests") == "requests"


def test_parse_requirement_simple():
    parsed = parse_requirement_line("requests==2.31.0")
    assert parsed is not None
    assert parsed["package_name"] == "requests"
    assert parsed["version"] == "2.31.0"
    assert parsed["constraint"] == "==2.31.0"


def test_parse_requirement_extras_and_marker():
    parsed = parse_requirement_line('uvicorn[standard]>=0.27; python_version>="3.11"')
    assert parsed is not None
    assert parsed["package_name"] == "uvicorn"
    assert "standard" in parsed["extras"]
    assert parsed["marker"] is not None


def test_parse_skips_comments_and_flags():
    assert parse_requirement_line("# comment") is None
    assert parse_requirement_line("-r other.txt") is None
    assert parse_requirement_line("") is None
