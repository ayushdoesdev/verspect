# Production deployment

Operator procedure for the first Verspect production host. This matches the current implementation (`docker-compose.prod.yml`, `backend/app/core/config.py`, `frontend/Dockerfile`).

Do **not** use `docker-compose.yml` (development: bind-mounts, Mailhog, `npm run dev`, no Redis password) for customer traffic.

Do **not** commit `.env`. Never print secrets.

Live `up` of the production stack on a laptop that already runs `depintel-*` on ports 3000/8000 is **MANUAL CONFIGURATION** — use a dedicated host.

---

## 1. Prerequisites

REQUIRED:

- Docker Engine + Docker Compose v2
- A dedicated host (or VM) with ports 80/443 free for a TLS reverse proxy
- Public DNS names for the app and API (can be the same host with path routing, or two hostnames)
- GitHub OAuth App
- SMTP server that is not Mailhog/localhost
- Unique secrets generated on the host (`openssl rand -hex 32`)

OPTIONAL:

- Stripe **or** Razorpay (evaluation works 7 days without them; paid checkout returns HTTP 503 until configured)
- Cloud AI keys (`openai` / `gemini` / `groq` / `openrouter`) — `AI_PROVIDER=ollama` is valid if Ollama is reachable
- Google OAuth (email/password and GitHub already exist)
- Slack incoming webhook

NOT REQUIRED:

- Development Compose, Mailhog, `NEXTAUTH_*` (unused by the application)
- `INTERNAL_API_URL` (Compose sets it; application code does not read it)
- Bootstrap admin variables (ignored when `APP_ENV=production`)
- C# / Kotlin support

---

## 2. Environment variables

Copy `.env.example` → `.env` on the production host, then replace every development placeholder. Production Settings (`APP_ENV=production` or `prod`) **reject** placeholder secrets, localhost public URLs, Mailhog SMTP, the development database password `depintel_secret`, Redis URLs without a password, `APP_DEBUG=true`, empty GitHub OAuth, and a cloud `AI_PROVIDER` without that vendor’s key.

Full names: [environment.md](environment.md).

### REQUIRED to boot production

| Variable | Notes |
|----------|--------|
| `APP_ENV` | `production` (Compose also sets this) |
| `APP_DEBUG` | Must be `false` (Compose sets this) |
| `SECRET_KEY` | ≥16 chars; not `change-me…` |
| `APP_URL` | Public frontend origin (CORS, OAuth redirects) |
| `API_URL` | Public API origin (OAuth callback, webhooks) |
| `ALLOWED_HOSTS` | Must include the `API_URL` hostname. Include `localhost` so the container healthcheck (`curl http://localhost:8000/health`) succeeds |
| `POSTGRES_PASSWORD` | Required by Compose interpolation |
| `REDIS_PASSWORD` | Required by Compose interpolation; also injected into Redis `--requirepass` |
| `GITHUB_CLIENT_ID` | GitHub OAuth App |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App |
| `GITHUB_REDIRECT_URI` | Must be `{API_URL}/api/v1/auth/github/callback` (public, not localhost) |
| `GITHUB_WEBHOOK_SECRET` | Unique; not `change-me-webhook-secret` |
| `SMTP_HOST` | Real mail host — not `localhost`, `127.0.0.1`, or `mailhog` |
| `NEXT_PUBLIC_APP_URL` | Baked into the frontend image; must not contain localhost |
| `NEXT_PUBLIC_API_URL` | Baked into the frontend image; must not contain localhost |

Compose **overrides** `DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` from `POSTGRES_*` / `REDIS_PASSWORD`. Those URLs must not contain `depintel_secret`, and Redis URLs must include the password (Compose does this).

If `AI_PROVIDER` is `openai`, `gemini`, `groq`, or `openrouter`, that provider’s API key is **REQUIRED**. `ollama` does not need a cloud key.

### OPTIONAL

| Variable | Notes |
|----------|--------|
| `APP_NAME` | API metadata |
| `POSTGRES_USER`, `POSTGRES_DB` | Compose defaults: `depintel` / `dependency_intelligence` |
| `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `SMTP_FROM` | Set a real `SMTP_FROM` on your domain |
| `BILLING_PROVIDER` | `stripe` (default) or `razorpay` |
| Stripe `STRIPE_*` keys, webhook secret, and `STRIPE_PRICE_{STARTER,PRO,TEAM}_{MONTHLY,YEARLY}` | REQUIRED for paid checkout; empty → HTTP 503 |
| Razorpay `RAZORPAY_*` keys, webhook secret, and `RAZORPAY_PLAN_*` | Same, when `BILLING_PROVIDER=razorpay` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google sign-in |
| `AI_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Default local path |
| `OPENAI_*`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_*` | Cloud AI |
| `AI_FALLBACK_PROVIDERS`, `AI_ENABLE_CLOUD_FALLBACK` | Cloud fallbacks stay off for Ollama unless enabled |
| `LLM_MODEL`, `LLM_TIMEOUT`, `LLM_MAX_TOKENS`, `LLM_SUMMARY_MAX_TOKENS`, `LLM_TEMPERATURE`, `AI_CACHE_TTL_SECONDS` | Caps and cache; default timeout is 180s |
| `SLACK_WEBHOOK_URL` | Alert notifications |
| `LICENSE_POLICY_REJECT`, `LICENSE_POLICY_WARN` | Defaults; orgs can override in settings |
| `SCAN_*`, `SIMULATION_*`, `WORKER_*`, `JOB_MAX_AUTO_RETRIES`, `QUEUE_BLOCKED_DEPTH_THRESHOLD` | Job lifecycle |
| `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes |
| `SCAN_CLONE_DIR`, `SCAN_MAX_FILE_SIZE_MB`, `SCAN_CONCURRENCY` | Scanner |

### NOT REQUIRED

| Variable | Notes |
|----------|--------|
| `NEXTAUTH_URL`, `NEXTAUTH_SECRET` | Unused by application code |
| `INTERNAL_API_URL` | Set by Compose; unused by application code |
| `BOOTSTRAP_ADMIN_*` | Ignored in production |
| Mailhog ports / `SMTP_HOST=mailhog` | Development only |

---

## 3. GitHub setup

REQUIRED:

1. Create a GitHub OAuth App (https://github.com/settings/developers).
2. Homepage URL = `APP_URL`.
3. Authorization callback URL = `{API_URL}/api/v1/auth/github/callback`.
4. Put Client ID / Secret in `.env`. Request scopes that cover private repositories the customer will import.

OPTIONAL (Pro / Team / Enterprise inbound push scans):

5. Generate a unique `GITHUB_WEBHOOK_SECRET`.
6. On import with webhooks enabled, Verspect registers `{API_URL}/api/v1/webhooks/github`.
7. Signature header must be `X-Hub-Signature-256` (HMAC SHA-256). Invalid signatures return 401.

Expected failures: revoked token → 401 “Reconnect GitHub”; missing repo permission → 403; rate limit → 429.

Migration PRs: `POST /api/v1/migration/simulations/{id}/pull-request` with `{ "confirm": true }` and Team/Enterprise entitlement. `confirm=false` is rejected. This never runs automatically.

---

## 4. Billing setup

OPTIONAL to boot. REQUIRED before customers can pay.

Plans in code: Evaluation (`free`), Starter, Pro, Team, Enterprise. Checkout SKUs: `starter`, `pro`, `team`.

Stripe (`BILLING_PROVIDER=stripe`):

- Dashboard webhook: `{API_URL}/api/v1/billing/webhooks/stripe` (also accepted at `{API_URL}/api/v1/webhooks/stripe`)
- Create products/prices for Starter / Pro / Team, monthly and yearly
- Set `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, and the six `STRIPE_PRICE_*` IDs

Razorpay (`BILLING_PROVIDER=razorpay`):

- Webhook: `{API_URL}/api/v1/billing/webhooks/razorpay` (also `{API_URL}/api/v1/webhooks/razorpay`)
- Create Plans in Razorpay → set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, and `RAZORPAY_PLAN_*`

Production never locally activates a paid plan. Checkout / change-plan without credentials returns **HTTP 503**. Development may still activate locally.

---

## 5. AI setup

OPTIONAL for scans (inventory, OSV, license, health still run). REQUIRED for Dynamic Intelligence / AI advisor on Pro+ when you want model output.

- `AI_PROVIDER=ollama` with reachable `OLLAMA_BASE_URL` (from Compose often `http://host.docker.internal:11434`) and `OLLAMA_MODEL` (default `qwen3:8b`)
- Or a cloud provider **plus** that provider’s API key
- Set `LLM_TIMEOUT` (seconds). Local 8B fills can take ~1 minute; default is 180

Expected states (not fake success): complete deterministic → no AI call; partial → AI fills missing categories; empty deterministic → AI investigates; unavailable / timeout / malformed → evidence preserved and the UI shows that state. No AI entitlement (Starter / expired evaluation) → AI is not called.

---

## 6. SMTP setup

REQUIRED to boot production (`SMTP_HOST` must be a real server).

Set `SMTP_FROM` to an address on your domain. Set `SMTP_PORT`, `SMTP_TLS`, `SMTP_USER`, and `SMTP_PASSWORD` to match the provider. Password reset and verification email will not arrive if SMTP is wrong — that is a real failure, not a silent success.

---

## 7. DNS / TLS

REQUIRED:

- DNS A/AAAA (or CNAME) for the app and API hostnames
- Reverse proxy (Caddy, nginx, Traefik) terminating TLS and forwarding:
  - `APP_URL` → `127.0.0.1:3000` (frontend standalone `node server.js`)
  - `API_URL` → `127.0.0.1:8000` (uvicorn)
- `APP_URL` / `API_URL` / `NEXT_PUBLIC_*` must be the **public https origins**, not `http://backend:8000`

Compose publishes `3000` and `8000` on the host for the proxy. Postgres (`5432`) and Redis (`6379`) are **not** published.

Rebuild the frontend image after any `NEXT_PUBLIC_*` change (values are compile-time).

---

## 8. Docker deployment

On a **dedicated** production host:

```bash
git clone <verspect-repo-url>
cd Verspect
cp .env.example .env
# Edit .env — unique secrets, public URLs, GitHub, SMTP, Redis/Postgres passwords
# Do not copy a development .env

docker compose -f docker-compose.prod.yml config >/dev/null
docker compose -f docker-compose.prod.yml up -d --build
```

What this does:

- Builds backend, worker, and frontend images (frontend CMD is `node server.js`; **no source bind-mount**)
- Starts Postgres + Redis (app network only, persistent volumes)
- Runs one-shot `alembic upgrade head` (`verspect-migrate`) before backend becomes healthy
- Starts backend (uvicorn, 2 workers), Celery worker (queues `default,scans,analysis,notifications`), beat, frontend

Validate Settings without dumping secrets (after images exist):

```bash
docker compose -f docker-compose.prod.yml run --rm --no-deps backend \
  python -c "from app.core.config import get_settings; s=get_settings(); assert s.is_production and not s.app_debug; print('production settings ok')"
```

Do **not** run `docker compose up` (dev file) on this host.

---

## 9. Database migration

Compose already runs `alembic upgrade head` via the `migrate` service before backend starts.

Manual (if needed):

```bash
docker compose -f docker-compose.prod.yml exec backend alembic current
docker compose -f docker-compose.prod.yml exec backend alembic heads
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

Current head: `017_upgrade_findings`.

`alembic check` may report autogenerate noise (server defaults / index names). That is **not** a missing revision. Do not generate a migration for it.

---

## 10. Health verification

```bash
docker compose -f docker-compose.prod.yml ps
curl -sf "$API_URL/health"                    # Postgres connectivity; 503 if DB down
curl -sf "$API_URL/api/ai/health"             # provider name, available, latency
curl -sf "$API_URL/api/v1/scans/worker-status" # Celery inspect (worker online / queue)
curl -sf "$APP_URL/" >/dev/null               # frontend HTML
```

| Check | How |
|-------|-----|
| Backend | `GET /health` → `status: healthy`, `checks.database: true` |
| Frontend | HTTP 200 on `APP_URL`; JS/CSS under `/_next/static/` |
| PostgreSQL | Compose `pg_isready` healthcheck; `/health` database check |
| Redis | Compose `redis-cli ping` with `REDISCLI_AUTH`; OAuth login fails if Redis is down |
| Celery worker | `worker-status` `online: true`; `docker compose logs worker` |
| Celery beat | `docker compose logs beat` — scheduled rescans / stale-job recovery |
| Scan running/failed | Repository page + `GET /api/v1/scans/{id}` (`status`, `error_message`, stages) |
| Upgrade analysis | Simulation `status` (`running` / `completed` / `failed`) and timeout/malformed AI fields |
| AI unavailable | `/api/ai/health` `available: false`; simulator keeps deterministic evidence |
| AI timeout | Simulation/UI timeout state (not “success”) |
| GitHub unavailable | 401/403/429 on import, sync, or PR |
| Billing unavailable | Checkout / change-plan HTTP 503 |

---

## 11. First customer test

Run on the **production** URLs after DNS/TLS. Expected success unless noted.

| Step | Success | Failure (must not look like success) |
|------|---------|--------------------------------------|
| Signup / login | Session JWT; email verify if SMTP works | Invalid credentials stay on login with error |
| Organization | Personal org on signup; switcher scopes data | Cross-org IDs → 404 |
| Connect GitHub | OAuth state consumed once; ticket exchanged over POST | Invalid/expired state → login error query |
| Import repository | Repo appears in org; private repos need token scope | 401 reconnect / 403 permission / 429 rate limit |
| Scan | Stages progress; worker-status explains delay | Failed/cancelled with `error_message`; no infinite spinner |
| Dependencies | Inventory from manifests/lockfiles | Unsupported language: explicit unsupported, no fake packages |
| Security | OSV matches stored as returned | Query failure is not “zero CVEs guaranteed” |
| License | SPDX + org policy | Unresolved license stays unresolved |
| Health | Score from observed signals | Missing signals → unresolved, not invented |
| Graph | Edges from lockfile/imports | Empty graph if no relationships |
| Upgrade Simulator | Evaluation (active) or paid | Expired evaluation → 402; previous reports remain |
| AI / Dynamic Intelligence | Pro+; merged deterministic + AI | Starter/expired → AI not called; timeout/malformed labeled |
| Migration Assistant | Team/Enterprise only | Starter/Pro → locked landing, not a dead “Coming Soon” button for supported langs |
| Review + confirm + PR | `{ confirm: true }` opens branch/commit/PR | `confirm=false` rejected; no patches → 400, no fake PR URL |
| Billing | Evaluation 7 days; checkout → Stripe/Razorpay | Unconfigured provider → 503; no local paid activation |

Also test:

- **Expired evaluation** — read-only; import/scan/simulator write blocked (402)
- **Starter** — simulator yes; AI advisor no; no migration assistant / PR
- **Pro** — AI advisor yes; migration assistant no
- **Team** — migration assistant + confirm PR yes
- **Invalid GitHub credentials** — reconnect, not a successful import
- **Unavailable AI / timeout** — deterministic evidence remains
- **Unsupported repository** — completed unsupported, no fabricated inventory
- **Cross-tenant access** — other org’s repo/scan/dependency IDs return 404

C# / Kotlin showing **Planned** is correct. Do not treat that as a dead implemented feature.

---

## 12. Backup / recovery

No separate backup product is bundled. Minimum operations:

**PostgreSQL backup**

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "verspect-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
```

Store the file off-box. Back up `.env` separately (secrets).

**PostgreSQL restore**

```bash
docker compose -f docker-compose.prod.yml stop backend worker beat frontend
gunzip -c backup.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose -f docker-compose.prod.yml exec backend alembic current
docker compose -f docker-compose.prod.yml start backend worker beat frontend
```

**Migration rollback**

1. Take a dump **before** `alembic upgrade`.
2. `docker compose -f docker-compose.prod.yml exec backend alembic downgrade <previous_revision>`
3. Prefer restoring the dump if the downgrade is data-lossy. Do not generate new revisions to “fix” `alembic check` noise.

**Service restart**

```bash
docker compose -f docker-compose.prod.yml restart backend
docker compose -f docker-compose.prod.yml restart worker beat
docker compose -f docker-compose.prod.yml restart frontend
docker compose -f docker-compose.prod.yml restart redis postgres
```

Volumes `postgres_data`, `redis_data`, and `scan_repos` persist across restarts. Redis is AOF (`appendonly yes`) with `noeviction`. Scan clones are ephemeral working copies; GitHub tokens must not remain in `.git/config` (the app scrubs remotes).

**Application recovery**

1. `docker compose -f docker-compose.prod.yml ps` — migrate must have succeeded once
2. `GET /health` — if 503, Postgres
3. `worker-status` — if offline, worker/Redis/broker URL
4. `GET /api/ai/health` — model/provider
5. Logs: `docker compose -f docker-compose.prod.yml logs --tail=200 backend worker beat frontend`

---

## 13. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Compose interpolation error | Missing `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, or `NEXT_PUBLIC_*` |
| Backend never healthy | Settings validation failed (placeholder secret, localhost URL, Mailhog, `depintel_secret`, Redis without password, empty GitHub OAuth) |
| Frontend talks to localhost | `NEXT_PUBLIC_*` baked at build time — rebuild image after changing them |
| Healthcheck fail, browser works | `ALLOWED_HOSTS` omitted `localhost` |
| OAuth “invalid session” | Redis down or callback URL ≠ GitHub App |
| Checkout 503 | Billing keys/price IDs unset (expected until configured) |
| Paid plan appeared without payment | Must not happen in production; restart with current code |
| AI “unavailable” vs timeout | Check `/api/ai/health` and `LLM_TIMEOUT`; do not treat timeout as success |
| Scan stuck queued | Worker offline or wrong queues — confirm worker command includes `scans,analysis` |
| 404 static JS | Dev/prod `.next` mix — production image must use `frontend/Dockerfile`, not bind-mount + `next dev` |

---

## 14. Security checklist

- `.env` is not in git; unique `SECRET_KEY` (JWT + Fernet for GitHub tokens)
- HTTPS on `APP_URL` / `API_URL`; Postgres and Redis not published
- GitHub OAuth state is one-time; login tickets are not JWTs in the redirect URL
- GitHub tokens encrypted at rest; clone remotes scrubbed
- Webhooks: GitHub HMAC; Stripe/Razorpay signatures verified; unsigned → 401/400
- Tenant isolation: org-scoped rows, cross-org 404
- Billing: owner/admin only; production no local paid activation; entitlements server-side
- AI: Pro+ advisor, Team+ migration; untrusted repo/changelog fenced; no invented CVEs/files/versions
- Migration PR: `confirm=true` + Team/Enterprise
- Production OpenAPI/docs disabled; bootstrap admin not created
- Logs: JSON in production; do not log tokens, passwords, or provider secrets
- Repository content, package metadata, and AI input remain untrusted

---

## 15. Rollback / recovery guidance

1. Keep the previous image tags or git revision that passed health checks.
2. Dump Postgres before every migrate.
3. To roll back application code: check out the last known-good revision, `docker compose -f docker-compose.prod.yml up -d --build`, confirm `/health`.
4. To roll back schema: restore the dump taken before migrate, or `alembic downgrade` only when that revision is known-safe.
5. To roll back a bad frontend URL bake: set correct `NEXT_PUBLIC_*`, rebuild frontend only.
6. Customer-facing incident: GitHub reconnect, billing 503, or AI timeout are **expected failure states** — do not ship a fake-success workaround.
