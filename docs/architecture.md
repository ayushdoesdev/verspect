# Architecture — Verspect

## System overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Next.js    │────▶│   FastAPI    │────▶│ PostgreSQL  │
│  Frontend   │     │   Backend    │     │             │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────┴───────┐
                    │    Redis     │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌─────────┐  ┌──────────┐
         │ Worker │  │  Beat   │  │  Mailhog │
         │ Celery │  │ Celery  │  │  (dev)   │
         └────┬───┘  └─────────┘  └──────────┘
              │
    GitHub clone → language pipeline → registry/OSV/license/health → optional AI
```

## Identity and access

- Users authenticate with GitHub OAuth (JWT access + refresh). Google and email signup are also available.
- GitHub tokens are stored encrypted (Fernet) and used for clone, listing, and opt-in PR publish.
- Repository access is scoped to the user's **active organization**. Cross-organization IDs return 404.

## Repository lifecycle

1. Connect GitHub and select repositories (private repos require a token with repo scope).
2. Import stores metadata on the organization. Pro+ may register inbound GitHub webhooks.
3. Clone to an ephemeral scan volume.
4. Language pipeline: classify → parse manifests/lockfiles → usage → graph → enrich.
5. Results persist: dependencies, relationships, usages, CVEs, licenses, health, alerts.

## Scan pipeline (Celery)

| Queue | Work |
|-------|------|
| `scans` | Clone, classify, parse, usage, graph persist |
| `analysis` | Registry versions, OSV, licenses, health, alternatives, optional AI summaries |
| `notifications` | Email / Slack for critical alerts |
| `default` | Recovery, cleanup, upgrade simulations |

Unsupported languages finish as unsupported. They do not invent a dependency inventory.

## Data model (high level)

Organizations, members, repositories, scans, dependencies, dependency relationships, library usages, CVEs, licenses (on the dependency), health (on the dependency + breakdown metadata), upgrade simulations, upgrade findings, migration reports / knowledge-base rules, AI caches, billing subscriptions and invoices.

## Security notes

- Tenant isolation is organization-scoped (`get_org_repository`).
- Repository file contents sent to AI are fenced as untrusted data.
- Production rejects default `SECRET_KEY` / `GITHUB_WEBHOOK_SECRET` values.
- Billing checkout in production requires a configured Stripe or Razorpay provider.

## Deployment

`docker compose up` for development. `docker compose -f docker-compose.prod.yml up -d --build` for production (migrations job, required secrets, no Mailhog, no source bind-mounts). Operator procedure: [production-deployment.md](production-deployment.md).
