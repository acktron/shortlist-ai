# ShortlistAI

ShortlistAI helps staffing recruiters screen CVs against a role, review ranked candidates with source evidence, and share a masked shortlist with client hiring teams. Scores help organize review; the system never automatically rejects a candidate.

## Features

- Versioned job scorecards with skill, experience, notice, CTC, and location criteria.
- Bulk PDF/DOCX CV upload, parsing, deduplication, PII redaction, and evidence-backed scoring.
- Recruiter review, shortlist submission, and a stage-based pipeline.
- A mobile-friendly client portal with masked candidate details and shortlist feedback.
- Delivery-head calibration, candidate access history, and data deletion workflows.
- Pluggable AI providers: Gemini, local Ollama, and deterministic mock mode.

## Local run

Requirements: Python 3.12, Docker Compose, Node.js, and npm. From the repository root:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
cp backend/.env.example backend/.env
```

Edit `backend/.env` for your setup. Use `AI_MODE=mock` for a deterministic demo without an AI service, `AI_MODE=ollama` with a local Ollama server, or `AI_MODE=gemini` with `GEMINI_API_KEY` configured. Start Postgres, apply migrations, and launch both apps with:

```bash
./dev.sh
```

The app is at <http://127.0.0.1:5173>; the API is at <http://127.0.0.1:8000>. `dev.sh` keeps the services running until interrupted.

For a fresh fictional demo dataset, run this in another terminal:

```bash
cd backend
./.venv/bin/python -m seed.seed --reset
```

## Demo accounts

All demo accounts use the demo-only password `Demo@1234`.

| Role | Email |
|---|---|
| Recruiter | `recruiter@companya.demo` |
| Delivery head | `head@companya.demo` |
| Meridian Bank client | `priya@meridianbank.demo` |
| Kestrel IT client | `rahul@kestrelit.demo` |

## Configuration

Backend environment variable names are listed in `backend/.env.example`. The main settings are:

- `DATABASE_URL` — PostgreSQL URL. For Neon, use the `postgresql+psycopg` driver and `sslmode=require`.
- `ENV`, `JWT_SECRET`, `JWT_EXPIRES_MIN`, and `CORS_ORIGINS`.
- `AI_MODE`, `AI_CONCURRENCY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_REQUEST_INTERVAL_SECONDS`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_VISION_MODEL`.
- `MAX_UPLOAD_MB` and `MAX_BATCH_FILES`.
- Frontend `VITE_API_URL` (defaults to `http://localhost:8000/api`).

For production, set `ENV=production`, provide a unique `JWT_SECRET`, a Neon `DATABASE_URL`, the Gemini API key, and the deployed frontend origin in `CORS_ORIGINS`. The API refuses to start in production with the development JWT secret. Do not commit `.env` files or secret values.

`./.venv/bin/python -m app.ai.check` (from `backend/`) makes one scorecard extraction and one CV scoring request with the configured provider and prints results with latency. It uses real Gemini calls when `AI_MODE=gemini`.

Gemini's free tier can rate-limit larger batches. If you hit free-tier limits, set `GEMINI_MODEL=gemini-2.5-flash-lite` and retry after the quota window resets.

## Tests and build

Tests always select the deterministic mock provider:

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest -q
cd ../frontend
npm run build
```

## Project structure

```text
backend/app/       FastAPI app, models, routers, services, and AI providers
backend/alembic/   Database migrations
backend/seed/      Fictional CV generation and end-to-end demo seed
backend/tests/     Service, access-control, pipeline, and API smoke tests
frontend/src/      React, TypeScript, API client, and recruiter/client screens
docs/SPEC.md       Product and implementation source of truth
```
