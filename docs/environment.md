# Environment variables

Copy `.env.example` to `.env`. Values below match the backend `Settings` model and Compose. Production procedure: [production-deployment.md](production-deployment.md).

**REQUIRED** / **OPTIONAL** / **NOT REQUIRED** refer to a production (`APP_ENV=production`) boot. Development may use the `.env.example` placeholders.

## Application

| Variable | Production | Purpose |
|----------|------------|---------|
| `APP_NAME` | OPTIONAL | Product name in API metadata |
| `APP_ENV` | REQUIRED | `development`, `beta`, or `production` (`prod` is treated as production) |
| `APP_DEBUG` | REQUIRED `false` | Verbose errors; **rejected if true in production** |
| `APP_URL` | REQUIRED | Frontend origin (CORS). **Must be a public origin in production** (not localhost) |
| `API_URL` | REQUIRED | Public API URL (OAuth callbacks, webhooks). **Must be a public origin in production** |
| `SECRET_KEY` | REQUIRED | JWT and Fernet material. **Must be unique in production** (default `change-me…` is rejected) |
| `ALLOWED_HOSTS` | REQUIRED | Comma-separated hostnames. **Must include the `API_URL` hostname in production** (include `localhost` as well so container healthchecks succeed) |

## Bootstrap admin (non-production only)

`BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_NAME`. **NOT REQUIRED** in production (ignored). Development/beta only.

## Database and jobs

| Variable | Production | Purpose |
|----------|------------|---------|
| `POSTGRES_*` | `POSTGRES_PASSWORD` REQUIRED | Compose Postgres credentials. |
| `DATABASE_URL` | REQUIRED (Compose sets) | Async SQLAlchemy URL. Production rejects the development `depintel_secret` password. |
| `DATABASE_URL_SYNC` | REQUIRED (Compose sets) | Alembic / sync URL |
| `REDIS_PASSWORD` | REQUIRED | Required by production Compose. Leave empty for local Compose. |
| `REDIS_URL` | REQUIRED (Compose sets) | App cache / OAuth state. **Production requires a password in the URL** |
| `CELERY_BROKER_URL` | REQUIRED (Compose sets) | Celery broker. **Production requires a password in the URL** |
| `CELERY_RESULT_BACKEND` | REQUIRED (Compose sets) | Celery results. **Production requires a password in the URL** |

Scan and simulation timeouts (`SCAN_*`, `SIMULATION_*`, `WORKER_*`, `JOB_MAX_AUTO_RETRIES`) are documented on `Settings` in `backend/app/core/config.py`.

## GitHub

| Variable | Production | Purpose |
|----------|------------|---------|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | REQUIRED | OAuth App |
| `GITHUB_REDIRECT_URI` | REQUIRED | Must match the OAuth App callback. **Must be the public API callback in production** |
| `GITHUB_WEBHOOK_SECRET` | REQUIRED | HMAC for inbound GitHub webhooks; unique in production |

## Google OAuth (optional)

`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` — **OPTIONAL**.

## AI

| Variable | Purpose |
|----------|---------|
| `AI_PROVIDER` | `ollama` \| `openai` \| `gemini` \| `groq` \| `openrouter` |
| `AI_FALLBACK_PROVIDERS` | Ordered cloud fallbacks |
| `AI_ENABLE_CLOUD_FALLBACK` | When provider is ollama, cloud fallbacks stay off unless true |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI |
| `GEMINI_API_KEY` | Gemini |
| `GROQ_API_KEY` | Groq |
| `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` | OpenRouter |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local Ollama (`host.docker.internal` from Compose) |
| `LLM_MODEL`, `LLM_TIMEOUT`, `LLM_MAX_TOKENS`, `LLM_SUMMARY_MAX_TOKENS`, `LLM_TEMPERATURE` | Generation caps. Development default: `LLM_TIMEOUT=180` (seconds). Production should set this explicitly. |
| `AI_CACHE_TTL_SECONDS` | Response cache TTL |

Missing AI keys disable those providers. Scans still complete without AI. `AI_PROVIDER=ollama` is **OPTIONAL** (valid without a cloud key). A cloud `AI_PROVIDER` **requires** that vendor’s API key in production.

## Billing

`BILLING_PROVIDER=stripe` or `razorpay`.

Stripe: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_{STARTER,PRO,TEAM}_{MONTHLY,YEARLY}`.

Razorpay: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_PLAN_{STARTER,PRO,TEAM}_{MONTHLY,YEARLY}`.

Without keys, development can activate a plan locally. Production checkout and change-plan return HTTP 503 until configured. Billing keys are **OPTIONAL** to boot (evaluation still works). They are **REQUIRED** before customers can pay.

## Frontend public URLs

`NEXT_PUBLIC_APP_URL` and `NEXT_PUBLIC_API_URL` are **REQUIRED** and **baked into the production frontend image**. Production Compose requires them; the image build fails if they are empty or contain `localhost`.

`NEXTAUTH_URL` and `NEXTAUTH_SECRET` are **NOT REQUIRED** (unused by the application). `INTERNAL_API_URL` is set by Compose and is **NOT REQUIRED** (unused by application code).

## Notifications and license defaults

`SMTP_HOST` is **REQUIRED** in production (not `localhost`, `127.0.0.1`, or `mailhog`). `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `SMTP_FROM` are OPTIONAL but should match the provider. `SLACK_WEBHOOK_URL`, `LICENSE_POLICY_REJECT`, `LICENSE_POLICY_WARN` are OPTIONAL. Organizations can override license policy in settings.

## Scanner

`SCAN_CLONE_DIR`, `SCAN_MAX_FILE_SIZE_MB`, `SCAN_CONCURRENCY`

JWT: `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`
