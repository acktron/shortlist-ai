# ShortlistAI status

Last verified: 2026-11-09

## Current capabilities

- Recruiter workflows for requisitions, scorecards, bulk PDF/DOCX uploads, parsing, duplicate handling, redaction, evidence review, candidate ranking, and client submission.
- Client portal scoped to each company, with masked candidate details, evidence quotes, shortlist/reject feedback, and interview proposals.
- Candidate profile/CV access logging, recruiter CV-open submission gate, stage history, pipeline transitions, calibration insights, consent status, and candidate data deletion.
- Mock, Ollama, and Gemini providers. Gemini uses structured Pydantic responses, request pacing, and transient-error retries. Scoring is deterministic from verified per-criterion evidence.
- Render backend Docker configuration, Neon-compatible PostgreSQL URLs, database health checks, Vercel SPA rewrites, production JWT checks, security headers, and production login rate limiting.

## Current local demo data

The requested `python -m seed.seed --reset` completed in mock mode: 2 clients, 4 users, 3 requisitions, 30 candidates, 30 applications, 31 scores, and 35 CV files. All scores use `model=mock`. The three failed files are intentional validation fixtures: `old_format.doc` (`unsupported_type`), `invoice.pdf` (`empty`), and `locked.pdf` (`password_protected`). The other files were processed into the demo dataset.

## Rate-limit handling

- Worker Gemini requests retry HTTP 429 up to five times, honoring `Retry-After` or waiting 20 seconds if it is absent. Gemini concurrency defaults to 1.
- If scoring still fails on a 429, the parsed candidate profile remains saved and the upload row shows `AI busy — Retry` with its Retry action.
- `seed --ai` processes selected files sequentially with a 7-second gap between Gemini requests and retries a rate-limited file with the mock provider. Its score is labeled `mock-fallback`.
- The previous live seed run hit the configured Gemini free-tier quota. A live `python -m app.ai.check` had succeeded; the full live seed was not rerun as part of this fix.

## Verification

- `pytest -q`: 69 passed.
- Local API health reports both the app and database as healthy; frontend and API run at `http://localhost:5173` and `http://localhost:8000`.

## Known limits

- Interview times can be proposed and confirmed in the app; calendar integration and invitation delivery are not implemented.
- CV blobs are stored in PostgreSQL for this demo rather than object storage.
- The live Gemini AI seed was not rerun after the retry/fallback changes; the local demo currently uses mock-scored data.
- Demo users share the password documented in `docs/SPEC.md`; production should use separate credentials and a production secret.
