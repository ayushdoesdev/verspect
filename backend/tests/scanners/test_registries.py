"""Registry metadata parsing without network."""

from app.scanners.registries import (
    CratesIoClient,
    MavenCentralClient,
    PackagistClient,
    RubyGemsClient,
)


def test_crates_extract_from_payload(monkeypatch) -> None:
    client = CratesIoClient()
    monkeypatch.setattr(
        client,
        "get_package_info",
        lambda name: {
            "crate": {
                "max_stable_version": "1.2.3",
                "description": "serde",
                "homepage": "https://serde.rs",
                "repository": "https://github.com/serde-rs/serde",
                "recent_downloads": 50000,
            },
            "versions": [
                {"num": "1.2.3", "created_at": "2024-01-01T00:00:00Z", "yanked": False, "license": "MIT"}
            ],
        },
    )
    info = client.extract_version_info("serde", "1.0.0")
    assert info["latest_version"] == "1.2.3"
    assert info["is_outdated"] is True
    assert info["license_raw"] == "MIT"
    assert info["download_count_month"] == 50000


def test_rubygems_extract(monkeypatch) -> None:
    client = RubyGemsClient()
    monkeypatch.setattr(
        client,
        "get_package_info",
        lambda name: {
            "version": "3.1.0",
            "licenses": ["MIT"],
            "homepage_uri": "https://example.com",
            "info": "A gem",
        },
    )
    info = client.extract_version_info("rails", "7.0.0")
    assert info["latest_version"] == "3.1.0"
    assert info["license_raw"] == "MIT"


def test_packagist_skips_dev(monkeypatch) -> None:
    client = PackagistClient()
    monkeypatch.setattr(
        client,
        "get_package_info",
        lambda name: {
            "packages": {
                "symfony/console": [
                    {"version": "dev-main", "license": ["MIT"]},
                    {"version": "v6.4.0", "license": ["MIT"], "description": "console", "time": "2024-01-01T00:00:00+00:00"},
                ]
            }
        },
    )
    info = client.extract_version_info("symfony/console", "6.0.0")
    assert info["latest_version"] == "6.4.0"


def test_maven_extract(monkeypatch) -> None:
    client = MavenCentralClient()
    monkeypatch.setattr(
        client,
        "get_package_info",
        lambda name: {"response": {"docs": [{"latestVersion": "6.1.0", "timestamp": 1700000000000}]}},
    )
    info = client.extract_version_info("org.springframework:spring-core", "6.0.0")
    assert info["latest_version"] == "6.1.0"
    assert info["is_outdated"] is True
