# Product

Verspect is a GitHub-connected SaaS that answers: which dependencies you use, which are outdated or vulnerable, whether an upgrade is likely to break **your** code, and how to migrate — with evidence.

## Journey

Connect repository → Scan → Inventory / graph / usage → Risk (OSV, license, health) → Analyze upgrade → Review impact → Generate patches (Team+) → Review diff → Confirm → Create GitHub PR.

## What is deterministic

- Manifest and lockfile parsing for supported ecosystems
- Direct vs lockfile/transitive edges when the lockfile is present
- Python AST usage; import/module usage for other languages
- Registry latest-version comparison
- OSV matches for the queried package name + version + ecosystem
- SPDX-style license detection and org policy (reject / warn / allow)
- Health scores from observed metrics only
- Catalog-backed upgrade findings (Python packages listed in `rule_catalog.py`)

A major version bump is **not** classified as breaking by itself.

## What AI does

Used when semantic reasoning is required and the plan allows it:

- Release-note interpretation
- Complex breaking-change reasoning when deterministic rules are missing
- Migration recommendations and patch drafts
- Alternative suggestions (Python knowledge base today)
- Repository-specific plans

AI output is structured JSON, fenced against prompt injection from repository files, and must not override deterministic facts. Low-confidence or unevidenced claims stay unresolved.

## Plans

| Plan id | Display | Role |
|---------|---------|------|
| `free` | Evaluation | 7-day evaluation, 1 repo, Upgrade Simulator, no AI migration |
| `starter` | Starter | 10 repos, exports, no AI migration |
| `pro` | Pro | Unlimited repos/scans, scheduled scans, GitHub inbound webhooks, AI Upgrade Advisor |
| `team` | Team | Seats, RBAC, audit, AI Migration Assistant |
| `enterprise` | Enterprise | Custom; SSO/SCIM/private AI are sales-assisted, not self-serve in this codebase |

Server-side entitlements enforce repository, scan, and AI/migration limits. Frontend plan badges are not trusted.

## Honest limitations

See [languages.md](languages.md).
