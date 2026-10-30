# Security and data handling

## Tenant isolation

All repository, scan, dependency, simulation, and migration routes resolve the **active organization** and load rows with `organization_id` (or via a repository that belongs to that org). Cross-tenant IDs return 404, not 403, to avoid existence leaks. Write actions require `owner`, `admin`, or `developer`. Viewers are read-only.

GitHub credentials belong to the acting user. PR publish uses that user's token, not another member's.

Billing customer IDs and invoices are organization-scoped.

## Secrets

- GitHub access tokens are encrypted at rest.
- Logs must not print tokens, Stripe/Razorpay secrets, or JWT secrets.
- Production process start fails if `SECRET_KEY` or `GITHUB_WEBHOOK_SECRET` are still the documented placeholders, if public URLs are localhost, if Redis has no password, if GitHub OAuth is empty, or if SMTP is Mailhog/localhost. See [production-deployment.md](production-deployment.md) §14.
- Bootstrap admin creation never runs in production.

## Authorization

- JWT on `/api/v1/*` except documented public/auth/webhook routes.
- Platform admin routes require `is_admin`.
- Plan limits (`assert_repo_limit`, `assert_scan_limit`, `require_feature`) run on the server.

## OAuth and GitHub

- OAuth state is one-time.
- 401/403/429 from GitHub are mapped to reconnect / permission / rate-limit errors.
- Migration PRs require `confirm: true` in the API body **and** a browser confirm in the UI.

## AI / prompt injection

Repository files, release notes, and package metadata are wrapped in `<<<UNTRUSTED_DATA` … `>>>END_UNTRUSTED_DATA`. System prompts instruct models to ignore instructions inside that block. AI must not invent deterministic facts (versions, CVE IDs, catalog replacements).

## Generated migrations

Only validated automatic patches with real file paths are eligible for PR publish. Snippet apply is first-occurrence replace of `current_code`. If GitHub contents no longer match, publish fails instead of force-patching. Validation (parser/formatter/linter/typecheck/tests where configured) must pass before success is claimed.

## Vulnerabilities and licenses

OSV results are stored as returned. Empty results mean "no match or query failed", not "guaranteed clean" when the query failed (failures are logged). Licenses come from registry/manifest text, not LLM guesses.
