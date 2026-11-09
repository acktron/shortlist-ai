#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "$FRONTEND_PID" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$ROOT"
API_ALREADY_RUNNING=0
FRONTEND_ALREADY_RUNNING=0
curl --fail --silent http://127.0.0.1:8000/health >/dev/null && API_ALREADY_RUNNING=1 || true
curl --fail --silent http://127.0.0.1:5173/ >/dev/null && FRONTEND_ALREADY_RUNNING=1 || true
if [[ "$API_ALREADY_RUNNING" == 1 && "$FRONTEND_ALREADY_RUNNING" == 1 ]]; then
  echo "ShortlistAI is already ready: http://127.0.0.1:5173 (API http://127.0.0.1:8000)"
  while curl --fail --silent http://127.0.0.1:8000/health >/dev/null && curl --fail --silent http://127.0.0.1:5173/ >/dev/null; do
    sleep 1
  done
  exit 0
fi
if [[ "$API_ALREADY_RUNNING" == 1 || "$FRONTEND_ALREADY_RUNNING" == 1 ]]; then
  echo "Only one ShortlistAI service is running on the requested ports. Stop it or start both services together." >&2
  exit 1
fi

docker compose up -d postgres
for attempt in $(seq 1 60); do
  if docker compose exec -T postgres pg_isready -U shortlist -d shortlist >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" == 60 ]]; then
    echo "Postgres did not become ready within 60 seconds." >&2
    exit 1
  fi
  sleep 1
done

if [[ ! -x "$ROOT/backend/.venv/bin/python" ]]; then
  echo "Create backend/.venv and install backend/requirements.txt before starting dev.sh." >&2
  exit 1
fi

cd "$ROOT/backend"
./.venv/bin/python -m alembic -c alembic.ini upgrade head
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cd "$ROOT/frontend"
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort &
FRONTEND_PID=$!

wait_for_url() {
  local url="$1"
  local process_id="$2"
  for attempt in $(seq 1 60); do
    if curl --fail --silent "$url" >/dev/null; then return 0; fi
    if ! kill -0 "$process_id" 2>/dev/null; then
      echo "Server exited before becoming ready: $url" >&2
      exit 1
    fi
    if [[ "$attempt" == 60 ]]; then
      echo "Server did not become ready within 60 seconds: $url" >&2
      exit 1
    fi
    sleep 1
  done
}

wait_for_url "http://127.0.0.1:8000/health" "$BACKEND_PID"
wait_for_url "http://127.0.0.1:5173/" "$FRONTEND_PID"
echo "ShortlistAI is ready: http://127.0.0.1:5173 (API http://127.0.0.1:8000)"

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
