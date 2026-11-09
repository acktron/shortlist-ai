# Codex prompts — paste one phase at a time

Before Phase 1: create an empty public GitHub repo, clone it, and copy `AGENTS.md` (root) and `docs/SPEC.md` into it.
Make the first commit yourself: `docs: add agent rules and build spec`.
After each phase: run the app and tests yourself, fix anything broken, then commit. Reviewers read the commit history.

Time budget (deadline 23:59 IST): P1 1h · P2 1h · P3 2.5h · P4 2h · P5 1.5h · P6 1.5h · P7 1h · docs + zip 1h · buffer 1h.
If you fall behind, drop the Insights page (P6) and the Gurugram React requisition. Never drop tests or the access-control rules.

---

## Phase 1 — Scaffold, DB, auth, roles (~1h)

```
Read AGENTS.md and docs/SPEC.md fully. Build Phase 1 only.

Backend (backend/):
- FastAPI app with config via pydantic-settings, SQLAlchemy 2.0 models for ALL tables in SPEC §2, Alembic initial migration.
- Auth: POST /api/auth/login (bcrypt, JWT), GET /api/auth/me. deps.py with get_current_user and require_role(*roles).
- Consistent error format from SPEC §5. CORS from CORS_ORIGINS.
- docker-compose.yml with Postgres 16 for local dev. .env.example with names from SPEC §9. .gitignore covering .env.
- A minimal seed that creates the 2 clients and 4 demo users from SPEC §1.
- pytest setup with a test database, and tests: login ok, wrong password 401, /me requires a token, require_role blocks the wrong role.

Frontend (frontend/):
- Vite + React + TS + Tailwind + shadcn/ui + TanStack Query + React Router.
- Design tokens from SPEC §6 (Inter, zinc greys, one indigo accent, 12px radius) in tailwind config + CSS variables.
- Typed API client with JWT handling and 401 → logout.
- Login screen with demo-account chips, role-based redirect: recruiter/delivery_head → /recruiter, client → /portal.
- App shell: recruiter layout (left nav: Requisitions, Insights for delivery_head) and portal layout (simple top bar, mobile-first).
- Shared components: PageHeader, EmptyState, ErrorState (with retry), Skeleton rows, StatusBadge.

Do not build later phases. Give me the exact commands to run backend, frontend and tests.
```

## Phase 2 — Requisitions + JD → scorecard (~1h)

```
Build Phase 2 per SPEC §3.1, §5, screens 2 and 3.
- app/ai/provider.py interface + factory with methods: extract_scorecard, transcribe_scan, extract_profile, score_cv.
  ollama.py (default now): httpx to OLLAMA_BASE_URL /api/chat, format = JSON schema from the Pydantic model, temperature 0,
  stream false, timeout 120s, validate with Pydantic and retry once with the validation error. Vision model for transcribe_scan.
  gemini.py: google-genai with response_schema JSON output, temperature 0, retry with backoff on 429/5xx (built now, used at deploy).
  mock.py deterministic keyword-based implementation of the same schema (used by tests).
  Choose by AI_MODE; if the chosen provider is unreachable at startup, log a warning and fall back to mock. Expose /api/meta
  with ai_mode + model so the UI shows a small badge ("Local AI · qwen2.5:7b" / "Demo AI").
  prompts.py holds versioned prompts (PROMPT_VERSION constant).
- Requisition CRUD, scorecard extract (returns draft + field_confidence + missing_fields), save as new version, get active.
- Default weights from SPEC. If the AI call fails, return an empty draft plus a warning; the UI must still allow manual entry.
- Screen 2 Requisitions list with counts, empty state "Create your first requisition".
- Screen 3 JD intake: paste JD, Extract with AI (loading state), editable scorecard: skill chips (add/remove, aliases), weight stepper 1–5, experience min/max, notice max days, CTC max LPA, location. Highlight low-confidence/missing fields in amber with a hint. Save → version number shown.
- Tests: criteria conversion from AI draft, version increments, only one active scorecard, recruiter-only access.
```

## Phase 3 — Bulk upload, parsing, dedupe, redaction (~2.5h, the hard part)

```
Build Phase 3 per SPEC §3.2 (validate → hash → extract → scan/OCR → profile → dedupe → redact). Scoring comes in Phase 4,
but leave the worker ready to call it.
- POST /api/requisitions/{id}/uploads accepts up to MAX_BATCH_FILES files; validate extension + magic bytes + size; store blobs;
  create cv_files rows (queued) and return the batch immediately. Reject the whole request only if > 500 files; otherwise bad files become failed rows with clear error codes.
- workers/batch_processor.py: asyncio queue started on app startup, semaphore GEMINI_CONCURRENCY, re-queues unfinished files on startup.
- services/parsing.py: pdfplumber text, two-column fallback, DOCX paragraphs + tables + headers, scan detection → provider.transcribe_scan, error codes password_protected / corrupt / empty / unsupported_type (legacy .doc message).
- services/dedupe.py: 3 layers exactly as SPEC; never delete; possible duplicates flagged for the recruiter.
- services/redaction.py: pure function redact(text, full_name) implementing every rule in SPEC §3.2.
- Profile extraction with pydantic validation, one retry with the error, sanity ranges.
- Create candidate + application (stage sourced) per file.
- GET /api/uploads/{batch_id} returns progress + per-file status; retry endpoints.
- Screen 4 Upload: drag & drop, client-side checks, polling every 2s, progress bar, per-file table with status badges, reason and Retry, summary (parsed / duplicates / needs review / failed).
- Tests: test_parsing.py, test_dedupe.py, test_redaction.py, test_upload_validation.py from SPEC §8. Generate small fixture files in tests/fixtures with reportlab/python-docx in a conftest helper.
```

## Phase 4 — Scoring with evidence + ranked list + candidate review (~2h)

```
Build Phase 4 per SPEC §3.2 Scoring / Evidence verification / Score maths / Prompt injection, screens 5 and 6.
- services/scoring.py (pure): deterministic experience/notice/ctc/location verdicts + aggregation, bands, confidence, needs_review, sort key.
- services/evidence.py (pure): quote verification against raw_text.
- Worker step: provider.score_cv(redacted_text wrapped in <cv> tags, scorecard) → verify evidence → compute score → store scores row including scoring_input, model, prompt_version, latency. Injection phrase detection adds a review reason.
- POST /requisitions/{id}/rescore for a new scorecard version (scoring only).
- Applications list endpoint with filters, search across ALL candidates incl. low band, pagination.
- GET /applications/{id} logs view_profile. GET /applications/{id}/cv streams the file, logs view_cv, sets recruiter_opened_at and moves sourced → screened.
- POST /applications/{id}/submit → 409 cv_not_opened if not opened.
- Screen 5 Ranked list exactly as SPEC §6.5 including the line "Ranks are suggestions. Nobody is rejected automatically."
- Screen 6 Candidate review split view: CV on the left (PDF via iframe/object URL from the /cv endpoint, or text for DOCX), criteria + quoted evidence on the right, clicking a quote highlights it in the text view, review reasons, duplicate banner with Merge / Not a duplicate, "Hidden from AI" note + "See what the AI saw" drawer, Submit to client (disabled with tooltip until CV opened — but the server enforces it too), Withdraw.
- Tests: test_scoring.py, test_evidence.py, test_injection.py, and submit-without-open 409.
```

## Phase 5 — Client portal + pipeline (~1.5h)

```
Build Phase 5 per SPEC §4, §5 Portal/Pipeline, screens 7 and 8.
- services/pipeline.py: allowed transitions table, writes stage_events, 422 with allowed list on invalid moves.
- Portal endpoints scoped by user.client_id and visible stages; 404 for anything else; portal serializer with masked contacts (first name + last initial, no email/phone, redacted CV text only). Log view_portal_profile.
- Feedback: shortlist / reject (reason_code required, note required for "other") / propose_interview (1–3 future slots). Recruiter can confirm a slot → interview.
- Screen 7 Pipeline kanban with counts, horizontal scroll on mobile, stage menu on each card.
- Screen 8 Portal, mobile-first: requisition list → candidate cards → detail with summary, top evidence, recruiter note; sticky bottom bar Shortlist / Reject / Propose interview; bottom sheets for reason and slots; confirmation toasts; status chip after action.
- Tests: test_access.py and test_pipeline.py from SPEC §8.
```

## Phase 6 — Seed data, polish, insights (~1.5h)

```
Build Phase 6.
- seed/generate_cvs.py + seed/seed.py exactly per SPEC §7, including every edge-case file, the 3 brief candidates verbatim, ~30 fictional ones, realistic stages, feedback and access logs. `python -m seed.seed --reset` must be idempotent.
- Insights page for delivery_head (SPEC §3.3) + access log viewer per candidate. Skip if behind schedule.
- Polish pass across every screen: loading skeletons, empty states, error states with retry, no dead buttons, mobile check at 375px for the portal, keyboard focus states, consistent spacing and type scale. Remove anything on screen that has no purpose.
- Security pass: no secrets committed, all inputs validated, rate-limit /auth/login (simple in-memory), security headers, file download only via authorised endpoints.
```

## Phase 7 — Deploy (~1h)

```
Prepare deployment:
- backend/Dockerfile (python:3.12-slim, uvicorn), start command runs `alembic upgrade head` then the server; a one-off seed command.
- render.yaml for the backend web service. Frontend vercel.json with SPA rewrites.
- Health endpoint GET /api/health.
- List every env var needed (names only) for Render and Vercel.
```
Then deploy: Neon (create DB, copy DATABASE_URL) → Render (Docker, env vars, run seed once) → Vercel (VITE_API_URL) → set CORS_ORIGINS to the Vercel URL. Test every demo login on the live URL and on your phone.

---

## After Phase 7, come back to Dia for:
TDD (with GitHub + live URL at the top, architecture, data model, flows, AI design, UI decisions, assumptions, cuts, next steps, cost/ROI numbers) and deployment.md.
