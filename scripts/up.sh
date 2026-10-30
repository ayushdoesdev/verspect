#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — fill in GitHub and OpenAI credentials."
fi
docker compose up --build "$@"
