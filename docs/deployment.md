# Deployment — ShortlistAI

**Live app:** https://shortlist-ai-wine.vercel.app
**API health:** https://shortlist-ai-api.onrender.com/api/health → `{"status":"ok","database":"ok"}`
**Repo:** https://github.com/acktron/shortlist-ai

> The backend is on Render's free plan and sleeps after 15 minutes idle. The first request after that can take ~50 seconds while it wakes up.

## Demo accounts (password `Demo@1234`)

| Role | Email | What to try |
|---|---|---|
| Recruiter | `recruiter@companya.demo` | Senior Java Developer → Scorecard, Upload, Candidates, open Ritika, "See what the AI saw", submit |
| Delivery head | `head@companya.demo` | Insights (calibration), access log |
| Client — Kestrel IT | `rahul@kestrelit.demo` | Portal on a phone: Shortlist / Reject / Propose interview |
| Client — Meridian Bank | `priya@meridianbank.demo` | Sees only KYC Analyst candidates (none of Kestrel's) |

Test CVs to upload are in `backend/seed/cvs/`. Upload 1–3 at a time on the live site, because the Gemini free tier is rate-limited.

## Hosting

| Part | Service | Notes |
|---|---|---|
| Frontend | Vercel | Root `frontend/`, Vite build, SPA rewrites in `frontend/vercel.json` |
| Backend | Render (Docker, free) | `backend/Dockerfile`; start runs `alembic upgrade head` then uvicorn on `$PORT`; health check `/api/health` |
| Database | Neon Postgres (US East, Ohio) | Same region as the Render service |
| AI | Google Gemini (Flash) | `AI_MODE=gemini`; tests use the mock provider |

## Environment variables (names only — values are set in each dashboard)

**Render (backend):** `DATABASE_URL` (`postgresql+psycopg://…?sslmode=require`), `JWT_SECRET`, `ENV=production`, `AI_MODE=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `AI_CONCURRENCY=1`, `CORS_ORIGINS` (the Vercel URL).
**Vercel (frontend):** `VITE_API_URL=https://shortlist-ai-api.onrender.com/api`

The API refuses to start in production with the development JWT secret. No secrets are committed; the git history was scanned.

## Deploy steps (reproducible)

1. **Neon:** create a project and copy the connection string; change the scheme to `postgresql+psycopg://`.
2. **Migrate and seed** (from your machine, once):
   ```bash
   cd backend && source .venv/bin/activate
   export DATABASE_URL="postgresql+psycopg://…?sslmode=require" AI_MODE=mock
   alembic upgrade head && python -m seed.seed --reset
   ```
3. **Render:** New Web Service → this repo → Docker, Dockerfile `./backend/Dockerfile`, build context `./backend`, region Ohio, free plan, env vars above, health check `/api/health`.
4. **Vercel:** Import repo → root `frontend` → Vite → set `VITE_API_URL` → Deploy.
5. Set `CORS_ORIGINS` on Render to the Vercel URL and redeploy.
6. Every push to `main` redeploys both automatically.

## Run locally

```bash
cp backend/.env.example backend/.env     # AI_MODE=mock | ollama | gemini
./dev.sh                                 # Postgres, migrations, backend :8000, frontend :5173
cd backend && ./.venv/bin/python -m seed.seed --reset
PYTHONPATH=. ./.venv/bin/pytest -q       # 70 tests, mock AI only
```

## Known limits

- Seeded scores use the deterministic mock provider (fast and reproducible). New uploads on the live site use real Gemini.
- Free-tier Gemini limits make 500-CV batches slow; the worker retries and paces requests, and the paid tier removes this limit.
- Interview slots are proposed and confirmed in-app only; no calendar or email delivery.
- CV files are stored in Postgres for the demo.
