#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
docker compose up -d
cd backend
.venv/bin/alembic upgrade head
(.venv/bin/python -m seed.seed --reset)
(.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT INT TERM
cd "$ROOT/frontend"
npm run dev -- --host 127.0.0.1 --port 5173
