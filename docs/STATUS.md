# ShortlistAI status

## Working

- Recruiter login, requisitions, scorecard versioning, bulk PDF/DOCX upload, parsing, duplicate handling, redaction, scoring, evidence review, and candidate ranking.
- Candidate profile/CV access logging, recruiter submission gate, stage history, and pipeline transitions.
- Client portal scoped to the client company, with masked identities/contact details, verified evidence, shortlist/reject feedback, and interview proposals.
- Delivery head calibration, candidate access logs, consent status, and candidate data deletion.
- Responsive recruiter, client, and insights screens at 375px and 1440px.

## Final verification (2026-11-09)

- `python -m seed.seed --reset`: 2 clients, 4 users, 3 requisitions, 30 seeded candidates, 30 seeded applications, 35 CV files, 53 stage events, and 12 access logs.
- `pytest -q`: 54 passed, twice. `npm run build` and `pyflakes backend/app backend/tests` passed.
- API walkthrough: uploaded and processed 3 new fictional CVs; retrieved the ranked top five; opened a top-five CV, submitted it, confirmed the client saw a masked profile, shortlisted it, and confirmed the recruiter pipeline move. All four demo logins returned the expected role-scoped views.
- Local services are running at `http://localhost:5173` and `http://localhost:8000`.

## Known limits and mocked behavior

- The local API currently uses Ollama (`qwen2.5:7b`). The three walkthrough uploads processed successfully. Tests and the default seed pipeline use the deterministic mock provider; pass `--ai` to seed with the configured provider.
- `GeminiProvider` currently delegates to the mock provider; production Gemini integration is not implemented.
- Scanned-PDF OCR is deterministic in mock mode. Real image-to-text OCR is not yet wired into the Ollama provider.
- Interview times are proposed in the portal and confirmed by a recruiter; there is no calendar integration or invitation delivery.
- CV blobs are stored in PostgreSQL for the demo rather than object storage. Demo users share the password documented in `docs/SPEC.md`.
