# Testing

## Backend

From Compose:

```bash
docker compose exec backend pytest -v
```

On the host (requires the backend virtualenv with bcrypt, celery, git, httpx, etc.):

```bash
cd backend && pytest -v
```

Notable suites:

- `tests/scanners/` — analyzers for each supported language, classification, manifests, OSV mapping, registries
- `tests/services/` — billing, entitlements, GitHub errors, upgrade impact, migration publish, scan recovery
- `tests/api/` — org isolation, OAuth security, health
- `tests/ai/` — untrusted prompt fencing, providers
- `tests/migration_engine/` — rule matching and patches

Assertions are not weakened to pass. Network is mocked in unit tests; live OSV/registry calls are not required for CI.

Apply migrations in an integration environment with:

```bash
docker compose exec backend alembic upgrade head
```

## Frontend

```bash
docker compose exec frontend npm test
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
```

Do **not** run `npm run build` inside the live Compose frontend (`next dev`). Production verification uses `NEXT_DIST_DIR=.next` (see `frontend/package.json`) or Compose:

```bash
docker compose -f docker-compose.prod.yml build frontend
```

A raw `docker build` of `frontend/Dockerfile` must pass public build-args (localhost is rejected):

```bash
docker build -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_APP_URL=https://app.example.com \
  --build-arg NEXT_PUBLIC_API_URL=https://api.example.com \
  -t verspect-frontend:local frontend
```

Vitest covers changelog/roadmap copy, simulator helpers, job stages, and a few UI units. There is no browser E2E suite in this repository.

## What "green" means

A release candidate should have: backend pytest passing in the Docker image, frontend tests + `tsc` + lint + `next build` succeeding. Host-venv collection errors from missing optional packages are not a product failure if Compose tests pass.
