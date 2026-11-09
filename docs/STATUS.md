# ShortlistAI status

Last verified: 2026-11-09

## Current capabilities

- Recruiter workflows for requisitions, scorecards, bulk PDF/DOCX uploads, parsing, duplicate handling, redaction, evidence review, candidate ranking, and submission to clients.
- Client portal scoped to each client company, with masked candidate details, evidence quotes, shortlist/reject feedback, and interview proposals.
- Candidate profile/CV access logging, recruiter CV-open submission gate, stage history, pipeline transitions, calibration insights, consent status, and candidate data deletion.
- Mobile-friendly recruiter, client, and insights screens.
- Pluggable mock, Ollama, and Gemini providers. Gemini uses structured Pydantic responses, bounded retries for transient errors, concurrency control, and a health check command (`python -m app.ai.check`). Evidence is verified against CV text and final scores are computed by the backend.
- Render backend Docker configuration, Neon-compatible PostgreSQL URLs, database-backed health check, Vercel SPA rewrites, production JWT checks, security headers, and production login rate limiting.

## Verification

- `pytest -q`: 64 passed on two consecutive runs.
- `npm run build`: passed. Vite reports existing React Router `use client` directives as ignored warnings.
- `docker build -t shortlist-ai-backend ./backend`: passed.
- `python -m app.ai.check`: completed one real Gemini scorecard extraction and one CV score with `gemini-2.5-flash`.
- Git history credential-pattern scan: no matching committed secrets found across 520 reachable Git objects.
- The local API and frontend are running at `http://localhost:8000` and `http://localhost:5173`.

## Gemini seed run

`AI_MODE=gemini` is configured in the local, gitignored `backend/.env`. The requested `python -m seed.seed --reset --ai` run selected the three brief candidates and five additional candidates for real AI processing; the remaining generated CVs use the mock provider. The configured Gemini key returned quota-related HTTP 429 errors during the seed run, including after retries. Those eight selected files correctly ended as `failed` with `ai_unavailable`; there are no real-AI scores or evidence quotes to report for them from this run. The check command had succeeded earlier. Retry those files or rerun the AI seed after Gemini quota is available.

Tests always use the deterministic mock provider. The ordinary seed command also uses mock AI unless `--ai` is supplied. The local database currently contains the reset seed data, including the failed AI files.

## Known limits

- Interview times can be proposed and confirmed in the app; calendar integration and invitation delivery are not implemented.
- CV blobs are stored in PostgreSQL for this demo rather than object storage.
- Live Gemini extraction and scoring were verified by the check command. The full AI seed was blocked by the configured account's quota, and scanned-PDF transcription was not separately exercised against the live service.
- Demo users share the password documented in `docs/SPEC.md`; production should use separate credentials and a production secret.
