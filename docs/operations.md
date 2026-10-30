# Operations

## Start locally

```bash
cp .env.example .env
# Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET
docker compose up --build
docker compose exec backend alembic upgrade head
```

See [environment.md](environment.md) for every variable.

## GitHub OAuth

1. Create a GitHub OAuth App at https://github.com/settings/developers
2. Homepage URL: `http://localhost:3000` (or `APP_URL`)
3. Callback: `{API_URL}/api/v1/auth/github/callback` (default `http://localhost:8000/api/v1/auth/github/callback`)
4. Copy Client ID / Secret into `.env`

Private repository import needs a token with access to those repositories. Revoked tokens return 401 ("Reconnect GitHub"). Rate limits return 429. Missing repo permissions return 403.

## Inbound GitHub webhooks

On import, Pro / Team / Enterprise can register a webhook to `{API_URL}/api/v1/webhooks/github`. `GITHUB_WEBHOOK_SECRET` must match. This is inbound GitHub → Verspect, not a customer outbound webhook product.

## Scan stages

1. Clone / update
2. Classify language / package manager
3. Parse manifests and lockfiles (direct vs lockfile/transitive where the lockfile is present)
4. Usage analysis (AST for Python; import/module analysis for other supported languages)
5. Registry metadata (PyPI, npm, Go, Maven Central, crates.io, Packagist, RubyGems)
6. OSV query (ecosystem-correct package names)
7. License detection + organization policy
8. Health score from **observed** signals only
9. Optional AI summaries / upgrade advisor (plan-gated)
10. Alerts

## Upgrade simulation and PRs

- Upgrade Simulator is deterministic analysis plus optional AI on eligible plans.
- AI Migration Assistant (Team+) can generate patches.
- `POST /api/v1/migration/simulations/{id}/pull-request` with `{ "confirm": true }` creates a branch, commits validated snippets, and opens a PR. It never runs automatically.

## Billing

Plans in code: `free` (Evaluation), `starter`, `pro`, `team`, `enterprise`. Checkout is `starter` / `pro` / `team`.

- Set `BILLING_PROVIDER=stripe` or `razorpay` and the matching keys/price IDs.
- Development may activate a plan locally when keys are absent.
- Production returns HTTP 503 if billing is not configured.
- Limits (repos, scans, AI/migration) are enforced on the server.

Stripe webhooks: `{API_URL}/api/v1/billing/webhooks/stripe` (also `{API_URL}/api/v1/webhooks/stripe`)  
Razorpay webhooks: `{API_URL}/api/v1/billing/webhooks/razorpay` (also `{API_URL}/api/v1/webhooks/razorpay`)

## Celery

Workers consume `scans`, `analysis`, `notifications`, and `default`. Beat schedules rescans, incremental queues, clone cleanup, and stale-job recovery. Heartbeats prevent the reaper from killing live long enrichments.

## Useful commands

```bash
docker compose logs -f backend worker beat
docker compose exec backend pytest -v
docker compose exec frontend npm test
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
```

## Frontend (dev vs production)

Local Compose (`docker compose up`) runs `npm run dev` from `frontend/Dockerfile.dev` with `NEXT_DIST_DIR=.next-dev`. Production builds use `NEXT_DIST_DIR=.next` and `output: "standalone"`. Never run `next build` in the live `next dev` container — even with separate distDirs, concurrent compilation can poison the webpack cache and make the browser request unhashed `/_next/static/chunks/main-app.js` while only hashed files exist (404).

Production Compose builds `frontend/Dockerfile` (standalone) and starts `node server.js`. It does **not** bind-mount source over `/app` and does **not** run `npm run build` at container start.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Required to **boot**: `APP_ENV=production`, unique `SECRET_KEY`, unique `GITHUB_WEBHOOK_SECRET`, public `APP_URL` / `API_URL` / `GITHUB_REDIRECT_URI`, `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, public `NEXT_PUBLIC_APP_URL` / `NEXT_PUBLIC_API_URL`, and an `SMTP_HOST` that is not Mailhog/localhost. Billing keys are optional to boot (checkout returns 503 until set).

Do not bind-mount source. Do not use this file on a host already running development Compose.

Operator checklist, backups, smoke tests, and troubleshooting: [production-deployment.md](production-deployment.md).
