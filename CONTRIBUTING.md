# Contributing to Verspect

Thanks for helping improve Verspect. For substantial changes, open an issue first to discuss the problem and proposed approach.

## Development setup

The supported full-stack development setup uses Docker Compose v2. Install Docker and Git, then from the repository root run:

```bash
cp .env.example .env
docker compose up --build -d
```

Configure local GitHub OAuth credentials in `.env` if you need sign-in and repository import. Never commit `.env`, credentials, private repository data, or user feedback screenshots. See [README.md](README.md), [environment configuration](docs/environment.md), and [testing instructions](docs/testing.md) for service details.

For frontend-only development, use Node.js 22 and run `npm ci`, `npm run dev` from `frontend/`. For backend-only development, use Python 3.13, install `backend/requirements.txt` in a virtual environment, and configure reachable PostgreSQL and Redis services.

## Checks

Before opening a pull request, run relevant checks. The usual frontend checks are:

```bash
cd frontend
npm test
npm run lint
npx tsc --noEmit
npm run build
```

Backend tests can run in Compose with:

```bash
docker compose exec backend pytest -v
```

Some integration checks require configured services. State clearly which commands you ran and include any failures or limitations. Do not claim a check passed if it was not run.

## Pull requests

- Keep changes focused and explain the user-visible or maintenance impact.
- Add or update tests for behavior changes.
- Update documentation when setup, configuration, or behavior changes.
- Include migration notes for schema or environment changes.
- Do not include secrets, real user data, private repository contents, or unapproved assets.
- Preserve third-party license notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- A pull request may be reviewed, revised, or declined; opening one does not guarantee acceptance.
