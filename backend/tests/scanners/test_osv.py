"""OSV ecosystem mapping and payload construction (no network)."""

from app.scanners.osv import (
    OSVClient,
    extract_fixed_version,
    osv_ecosystem_name,
    package_name_for_osv,
    severity_from_osv,
)


def test_osv_ecosystem_mapping() -> None:
    assert osv_ecosystem_name("PyPI") == "PyPI"
    assert osv_ecosystem_name("pypi") == "PyPI"
    assert osv_ecosystem_name("npm") == "npm"
    assert osv_ecosystem_name("Go") == "Go"
    assert osv_ecosystem_name("Maven") == "Maven"
    assert osv_ecosystem_name("crates.io") == "crates.io"
    assert osv_ecosystem_name("crates") == "crates.io"
    assert osv_ecosystem_name("Packagist") == "Packagist"
    assert osv_ecosystem_name("RubyGems") == "RubyGems"


def test_maven_name_is_not_pep503_hyphenated() -> None:
    name = "org.springframework:spring-core"
    assert package_name_for_osv(name, "Maven") == name
    assert "-" not in package_name_for_osv(name, "Maven").split(":")[0].replace("org.springframework", "")


def test_pypi_name_is_pep503() -> None:
    assert package_name_for_osv("Django_REST_framework", "PyPI") == "django-rest-framework"


def test_npm_name_is_lowercased_scoped() -> None:
    assert package_name_for_osv("@Angular/Core", "npm") == "@angular/core"


def test_go_module_path_unchanged() -> None:
    path = "github.com/gin-gonic/gin"
    assert package_name_for_osv(path, "Go") == path


def test_query_payload_maven_keeps_colon() -> None:
    client = OSVClient()
    payload = client._query_payload("org.springframework:spring-core", "6.0.0", "Maven")
    assert payload["package"]["ecosystem"] == "Maven"
    assert payload["package"]["name"] == "org.springframework:spring-core"
    assert payload["version"] == "6.0.0"


def test_query_package_uses_cache(monkeypatch) -> None:
    client = OSVClient()
    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"vulns": [{"id": "GHSA-test"}]}

    class _Http:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, json):
            calls["n"] += 1
            assert json["package"]["name"] == "requests"
            return _Resp()

    monkeypatch.setattr("app.scanners.osv.httpx.Client", lambda **kwargs: _Http())
    first = client.query_package("Requests", "2.31.0", "PyPI")
    second = client.query_package("requests", "2.31.0", "pypi")
    assert first == second == [{"id": "GHSA-test"}]
    assert calls["n"] == 1


def test_extract_fixed_version_maven() -> None:
    vuln = {
        "affected": [
            {
                "package": {"name": "org.springframework:spring-core", "ecosystem": "Maven"},
                "ranges": [{"events": [{"introduced": "5.0.0"}, {"fixed": "5.3.39"}]}],
            }
        ]
    }
    fixed, introduced, _ = extract_fixed_version(
        vuln, "org.springframework:spring-core", "Maven"
    )
    assert fixed == "5.3.39"
    assert introduced == "5.0.0"


def test_severity_from_cvss() -> None:
    mapped, score, _ = severity_from_osv(
        {"severity": [{"type": "CVSS_V3", "score": 9.8}]}
    )
    assert mapped == "critical"
    assert score == 9.8


def test_osv_failure_is_unavailable_not_empty(monkeypatch) -> None:
    from app.scanners.osv import OSVUnavailableError

    client = OSVClient()

    def boom(*_args, **_kwargs):
        raise RuntimeError("osv timeout")

    monkeypatch.setattr(client, "query_package", boom)
    try:
        client.check_dependency("requests", "2.31.0", "PyPI")
        raise AssertionError("expected OSVUnavailableError")
    except OSVUnavailableError:
        pass
