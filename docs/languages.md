# Languages, package managers, and analysis limits

This document describes **implemented** scanners. If a capability is not listed, Verspect does not claim it.

## Python

- Manifests: `requirements*.txt`, `pyproject.toml`, Poetry, uv, Pipenv, `setup.py` / `setup.cfg`
- Lockfiles: `poetry.lock`, `uv.lock`, `Pipfile.lock` (transitive when present)
- Usage: Python AST — imports, calls, attributes, with evidence file/line
- Registry: PyPI JSON + download stats
- Upgrade catalog: pydantic, numpy, FastAPI (`on_event`), Flask (`before_first_request`), Django (`ugettext*`)
- Alternatives knowledge base: Python packages only

## JavaScript / TypeScript

- Manifests: `package.json`
- Lockfiles: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`
- Usage: import / require / export specifiers (not full call-graph / TypeScript type checker API analysis)
- Registry: npm

## Go

- Manifests: `go.mod`
- Lockfiles: `go.sum` (module versions)
- Usage: import paths
- Registry: proxy.golang.org when available; missing metadata is recorded, not invented

## Java

- Maven `pom.xml`
- Gradle files: **literal** `group:name:version` coordinates only. Version catalogs and Groovy/Kotlin script evaluation are not executed.
- Usage: `import` statements
- Registry: Maven Central search
- OSV: package name is `groupId:artifactId` (not PEP 503 hyphenated)

## Rust

- `Cargo.toml` / `Cargo.lock`
- Usage: `use` and `extern crate`
- Registry: crates.io (`recent_downloads` may feed popularity when present)

## PHP

- `composer.json` / `composer.lock`
- Usage: `use` / `require` / `include`
- Registry: Packagist

## Ruby

- `Gemfile` / `Gemfile.lock`
- Usage: `require` / `require_relative`
- Registry: RubyGems (license/homepage/version; lifetime download counts are **not** treated as monthly popularity)

## Shared (all supported ecosystems)

- Direct vs lockfile edges persisted on `dependency_relationships`
- OSV lookups use ecosystem-correct names
- License strings from registry/POM metadata when present
- Health: only observed signals (release recency, frequency from release dates, downloads when monthly/recent, vulns). GitHub stars and open issues are used only if populated; they are not guessed.

## Not implemented (do not expect)

- API call-graph / renamed-symbol analysis for non-Python languages
- Fabricated breaking changes from major-version number alone
- Public API keys / customer outbound webhooks / self-serve SSO/SCIM
- GitLab / Bitbucket import
- Unattended GitHub PRs (opt-in confirm only)
