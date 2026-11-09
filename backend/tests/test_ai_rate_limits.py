import asyncio

import pytest
from app.ai.errors import AIUnavailableError
from app.ai.gemini import _retry_after_seconds
from app.ai.schemas import Profile
from app.db import SessionLocal
from app.models import Application, Candidate, CvBlob, CvFile, Requisition, Score, StageEvent, UploadBatch, User
from app.services.parsing import ParsedDocument
from app.workers import batch_processor


def test_worker_honors_retry_after_for_rate_limits(monkeypatch):
    delays = []
    attempts = 0

    async def sleep(delay):
        delays.append(delay)

    async def request():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise AIUnavailableError("Busy", status_code=429, retry_after_seconds=4.5)
        return "ok"

    monkeypatch.setattr(batch_processor.asyncio, "sleep", sleep)

    assert asyncio.run(batch_processor._call_ai(request)) == "ok"
    assert attempts == 3
    assert delays == [4.5, 4.5]


def test_worker_uses_default_and_stops_after_five_rate_limit_retries(monkeypatch):
    delays = []
    attempts = 0

    async def sleep(delay):
        delays.append(delay)

    async def request():
        nonlocal attempts
        attempts += 1
        raise AIUnavailableError("Busy", status_code=429)

    monkeypatch.setattr(batch_processor.asyncio, "sleep", sleep)

    with pytest.raises(AIUnavailableError):
        asyncio.run(batch_processor._call_ai(request))

    assert attempts == 6
    assert delays == [20] * 5


def test_gemini_retry_after_header_is_extracted():
    class Response:
        headers = {"Retry-After": "12.5"}

    class RateLimitError(Exception):
        response = Response()

    assert _retry_after_seconds(RateLimitError()) == 12.5


def test_scoring_rate_limit_keeps_parsed_candidate(schema, monkeypatch):
    session = SessionLocal()
    requisition = session.query(Requisition).first()
    recruiter = session.query(User).filter_by(email="recruiter@companya.demo").one()
    batch = UploadBatch(
        requisition_id=requisition.id,
        uploaded_by=recruiter.id,
        total=1,
        processed=0,
        failed=0,
        duplicates=0,
        status="processing",
    )
    session.add(batch)
    session.flush()
    cv_file = CvFile(
        batch_id=batch.id,
        filename="rate_limited.pdf",
        mime="application/pdf",
        size_bytes=8,
        status="queued",
        attempts=0,
    )
    session.add(cv_file)
    session.flush()
    session.add(CvBlob(cv_file_id=cv_file.id, data=b"%PDFfake"))
    session.commit()

    async def sleep(_delay):
        return None

    class RateLimitedProvider:
        model = "gemini-2.5-flash"

        async def extract_profile(self, _text):
            return Profile(
                full_name="Rate Candidate",
                email="rate-candidate@example.demo",
                phone="+919111111111",
                current_role="Java Developer",
                total_exp_years=6,
                skills=["Java"],
                location="Noida",
            )

        async def score_cv(self, _text, _scorecard):
            raise AIUnavailableError("Busy", status_code=429, retry_after_seconds=0)

    monkeypatch.setattr(batch_processor, "parse_file", lambda *_args: ParsedDocument(
        "Rate Candidate\nExperience: 6 years\nSkills: Java\nLocation: Noida",
        "pdf_text",
    ))
    monkeypatch.setattr(batch_processor, "get_provider", lambda: RateLimitedProvider())
    monkeypatch.setattr(batch_processor.asyncio, "sleep", sleep)

    asyncio.run(batch_processor.process_file(cv_file.id))

    session.expire_all()
    cv_file = session.get(CvFile, cv_file.id)
    assert cv_file.status == "failed"
    assert cv_file.error_code == "ai_unavailable"
    assert cv_file.error_message == "AI busy — Retry"
    assert cv_file.candidate_id is not None
    candidate = session.get(Candidate, cv_file.candidate_id)
    application = session.query(Application).filter_by(candidate_id=candidate.id).one()
    assert candidate.full_name == "Rate Candidate"
    assert candidate.total_exp_years == 6
    assert candidate.redacted_text
    assert session.query(Score).filter_by(application_id=application.id).count() == 0
    candidate_id = candidate.id
    application_id = application.id
    file_id = cv_file.id
    batch_id = batch.id
    session.query(StageEvent).filter_by(application_id=application_id).delete()
    session.query(Application).filter_by(id=application_id).delete()
    session.query(CvBlob).filter_by(cv_file_id=file_id).delete()
    session.query(CvFile).filter_by(id=file_id).delete()
    session.query(Candidate).filter_by(id=candidate_id).delete()
    session.query(UploadBatch).filter_by(id=batch_id).delete()
    session.commit()
    session.close()


def test_seed_falls_back_to_mock_for_persistent_rate_limit(schema, monkeypatch):
    from seed import seed as seed_module

    session = SessionLocal()
    cv_file = session.query(CvFile).filter_by(filename="smoke.pdf").one()
    score = session.query(Score).one()
    file_id = cv_file.id
    score_id = score.id
    monkeypatch.setattr(seed_module, "SessionLocal", SessionLocal)
    attempts = []

    async def fake_process_file(file_id):
        attempts.append(seed_module.settings.ai_mode)
        with SessionLocal() as row_session:
            row = row_session.get(CvFile, file_id)
            if seed_module.settings.ai_mode == "gemini":
                row.status = "failed"
                row.error_code = "ai_unavailable"
                row.error_message = "AI busy — Retry"
            else:
                row.status = "done"
                row.error_code = None
                row.error_message = None
            row_session.commit()

    monkeypatch.setattr(seed_module, "process_file", fake_process_file)
    original_mode = seed_module.settings.ai_mode
    try:
        asyncio.run(seed_module._process_files([(cv_file.id, "pooja_nair.pdf")], "gemini", True))
    finally:
        seed_module.settings.ai_mode = original_mode

    session.expire_all()
    cv_file = session.get(CvFile, file_id)
    score = session.get(Score, score_id)
    assert attempts == ["gemini", "mock"]
    assert cv_file.status == "done"
    assert score.model == "mock-fallback"
    score.model = "mock"
    session.commit()
    session.close()
