"""Create a complete fictional demo dataset and process its CVs."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from passlib.context import CryptContext
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import (
    AccessLog,
    Application,
    Candidate,
    Client,
    ClientFeedback,
    CvBlob,
    CvFile,
    Requisition,
    Role,
    Score,
    Scorecard,
    StageEvent,
    UploadBatch,
    User,
)
from app.workers.batch_processor import process_file
from seed.generate_cvs import main as generate_cvs

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
CV_DIR = Path(__file__).parent / "cvs"
REAL_AI_FILENAMES = {
    "ritika_bansal.pdf",
    "arjun_rawat.docx",
    "pooja_nair.pdf",
    "java_01.pdf",
    "java_02.pdf",
    "kyc_01.pdf",
    "kyc_02.pdf",
    "react_01.pdf",
}
REAL_AI_REQUEST_INTERVAL_SECONDS = 7


def _criteria(kind: str) -> list[dict]:
    if kind == "java":
        return [
            {"id": "java", "kind": "must_skill", "label": "Java", "weight": 3, "params": {}},
            {"id": "spring-boot", "kind": "must_skill", "label": "Spring Boot", "weight": 3, "params": {"aliases": ["Spring"]}},
            {"id": "microservices", "kind": "must_skill", "label": "Microservices", "weight": 3, "params": {"aliases": ["microservice"]}},
            {"id": "kafka", "kind": "nice_skill", "label": "Kafka", "weight": 1, "params": {}},
            {"id": "aws", "kind": "nice_skill", "label": "AWS", "weight": 1, "params": {}},
            {"id": "experience", "kind": "experience", "label": "Experience", "weight": 3, "params": {"min_years": 5, "max_years": 8}},
            {"id": "notice", "kind": "notice", "label": "Notice period", "weight": 2, "params": {"max_days": 60}},
            {"id": "ctc", "kind": "ctc", "label": "Expected CTC", "weight": 1, "params": {"max_lpa": 28}},
            {"id": "location", "kind": "location", "label": "Location", "weight": 1, "params": {}},
        ]
    if kind == "kyc":
        return [
            {"id": "kyc", "kind": "must_skill", "label": "KYC", "weight": 3, "params": {}},
            {"id": "aml", "kind": "must_skill", "label": "AML", "weight": 3, "params": {}},
            {"id": "excel", "kind": "must_skill", "label": "Excel", "weight": 3, "params": {}},
            {"id": "cdd", "kind": "nice_skill", "label": "CDD", "weight": 1, "params": {}},
            {"id": "sanctions", "kind": "nice_skill", "label": "Sanctions screening", "weight": 1, "params": {}},
            {"id": "experience", "kind": "experience", "label": "Experience", "weight": 3, "params": {"min_years": 2, "max_years": 5}},
            {"id": "notice", "kind": "notice", "label": "Notice period", "weight": 2, "params": {"max_days": 30}},
            {"id": "location", "kind": "location", "label": "Location", "weight": 1, "params": {}},
        ]
    return [
        {"id": "react", "kind": "must_skill", "label": "React", "weight": 3, "params": {"aliases": ["React.js"]}},
        {"id": "typescript", "kind": "must_skill", "label": "TypeScript", "weight": 3, "params": {"aliases": ["TS"]}},
        {"id": "javascript", "kind": "must_skill", "label": "JavaScript", "weight": 3, "params": {"aliases": ["JS"]}},
        {"id": "accessibility", "kind": "nice_skill", "label": "Accessibility", "weight": 1, "params": {}},
        {"id": "experience", "kind": "experience", "label": "Experience", "weight": 3, "params": {"min_years": 3, "max_years": 6}},
        {"id": "notice", "kind": "notice", "label": "Notice period", "weight": 2, "params": {"max_days": 45}},
        {"id": "location", "kind": "location", "label": "Location", "weight": 1, "params": {}},
    ]


def _files_for(kind: str) -> list[Path]:
    if kind == "java":
        names = [
            "ritika_bansal.pdf", "ritika_bansal_copy.pdf", "ritika_bansal_v2.docx", "pooja_nair.pdf",
            "two_column.pdf", "personal_details.pdf", "scanned.pdf", "locked.pdf", "old_format.doc",
            "invoice.pdf", "injection.pdf", "possible_duplicate.pdf", "very_short.pdf",
        ]
        names.extend(f"java_{index:02d}.pdf" for index in range(1, 11))
    elif kind == "kyc":
        names = ["arjun_rawat.docx", "tables.docx"] + [f"kyc_{index:02d}.pdf" for index in range(1, 7)]
    else:
        names = [f"react_{index:02d}.pdf" for index in range(1, 5)]
    return [CV_DIR / name for name in names]


def _stage_event(db, application: Application, target: str, actor_id, note: str | None = None) -> None:
    previous = application.stage
    application.stage = target
    if target == "submitted" and application.submitted_at is None:
        application.submitted_at = datetime.now(timezone.utc)
        application.submitted_by = actor_id
    db.add(StageEvent(application_id=application.id, from_stage=previous, to_stage=target, actor_id=actor_id, note=note))


def _open_application(db, application: Application, candidate: Candidate, recruiter: User, at: datetime) -> None:
    if application.recruiter_opened_at is None:
        application.recruiter_opened_at = at
        if application.stage == "sourced":
            _stage_event(db, application, "screened", recruiter.id, "Recruiter opened the CV")
        db.add(AccessLog(user_id=recruiter.id, candidate_id=candidate.id, action="view_cv"))


def _add_feedback(db, application: Application, client_user: User, action: str, reason: str | None = None, note: str | None = None, slots: list | None = None) -> None:
    db.add(ClientFeedback(application_id=application.id, client_user_id=client_user.id, action=action, reason_code=reason, note=note, proposed_slots=slots))
    db.add(AccessLog(user_id=client_user.id, candidate_id=application.candidate_id, action="view_portal_profile"))


def _record_demo_activity(db, recruiter: User, priya: User, rahul: User) -> None:
    now = datetime.now(timezone.utc)
    apps = db.query(Application).all()
    candidate_by_code = {candidate.candidate_code: candidate for candidate in db.query(Candidate).all()}
    app_by_code_req: dict[tuple[str, str], Application] = {}
    for application in apps:
        candidate = db.get(Candidate, application.candidate_id)
        requisition = db.get(Requisition, application.requisition_id)
        app_by_code_req[(candidate.candidate_code, requisition.title)] = application
        if candidate.candidate_code in {"CND-91022", "CND-91047", "CND-91088", "CND-92001", "CND-92002", "CND-93001", "CND-93002"}:
            _open_application(db, application, candidate, recruiter, now - timedelta(days=1))

    # Four Java applications have been sent to Kestrel, including Ritika.
    java_codes = ("CND-91022", "CND-91088", "CND-92001", "CND-92002")
    java_apps = []
    for code in java_codes:
        application = app_by_code_req.get((code, "Senior Java Developer"))
        candidate = candidate_by_code.get(code)
        if not application or not candidate:
            continue
        _open_application(db, application, candidate, recruiter, now - timedelta(days=2))
        if application.stage != "submitted":
            _stage_event(db, application, "submitted", recruiter.id, "Submitted to Kestrel IT Services")
        java_apps.append(application)
    if len(java_apps) == 4:
        ritika_app, pooja_app, interview_app, _submitted_app = java_apps
        _stage_event(db, ritika_app, "shortlisted", rahul.id, "Client shortlisted")
        _add_feedback(db, ritika_app, rahul, "shortlist", note="Strong match for the platform team.")
        _stage_event(db, pooja_app, "client_rejected", rahul.id, "Notice period exceeds the role limit")
        _add_feedback(db, pooja_app, rahul, "reject", reason="notice_period", note="The 90 day notice period is outside our hiring timeline.")
        _stage_event(db, interview_app, "shortlisted", rahul.id, "Client shortlisted; interview slots proposed")
        slots = [(now + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(), (now + timedelta(days=4)).replace(hour=14, minute=0, second=0, microsecond=0).isoformat()]
        _add_feedback(db, interview_app, rahul, "propose_interview", note="Please choose one of these interview times.", slots=slots)

    # Two KYC candidates were submitted to Meridian; they are shown later in the funnel.
    kyc_codes = ("CND-91047", "CND-93001")
    kyc_apps = []
    for code in kyc_codes:
        application = app_by_code_req.get((code, "KYC Analyst"))
        candidate = candidate_by_code.get(code)
        if not application or not candidate:
            continue
        _open_application(db, application, candidate, recruiter, now - timedelta(days=3))
        if application.stage != "submitted":
            _stage_event(db, application, "submitted", recruiter.id, "Submitted to Meridian Bank")
        kyc_apps.append(application)
    if len(kyc_apps) == 2:
        offered_app, joined_app = kyc_apps
        _stage_event(db, offered_app, "shortlisted", priya.id, "Client shortlisted")
        _add_feedback(db, offered_app, priya, "shortlist", note="Proceed to offer discussion.")
        _stage_event(db, offered_app, "interview", recruiter.id, "Recruiter confirmed client interview")
        _stage_event(db, offered_app, "offered", recruiter.id, "Offer approved")
        _stage_event(db, joined_app, "shortlisted", priya.id, "Client shortlisted")
        _add_feedback(db, joined_app, priya, "shortlist", note="Selected after final interview.")
        _stage_event(db, joined_app, "interview", recruiter.id, "Recruiter confirmed client interview")
        _stage_event(db, joined_app, "offered", recruiter.id, "Offer approved")
        _stage_event(db, joined_app, "joined", recruiter.id, "Candidate joined")


def _summary(db) -> dict[str, int]:
    return {
        "clients": db.query(Client).count(),
        "users": db.query(User).count(),
        "requisitions": db.query(Requisition).count(),
        "candidates": db.query(Candidate).count(),
        "applications": db.query(Application).count(),
        "scores": db.query(Score).count(),
        "cv_files": db.query(CvFile).count(),
        "failed_files": db.query(CvFile).filter(CvFile.status == "failed").count(),
        "needs_review": db.query(Score).filter(Score.needs_review.is_(True)).count(),
        "stage_events": db.query(StageEvent).count(),
        "access_logs": db.query(AccessLog).count(),
        "client_feedback": db.query(ClientFeedback).count(),
    }


def _delete_all(db) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()


def seed(reset: bool = False, use_ai: bool = False) -> dict[str, int]:
    Base.metadata.create_all(engine)
    generate_cvs()
    db = SessionLocal()
    if reset:
        _delete_all(db)
    elif db.query(User).filter_by(email="recruiter@companya.demo").first():
        summary = _summary(db)
        print(f"Seed already present; no changes made: {summary}")
        db.close()
        return summary

    meridian = Client(name="Meridian Bank", industry="Banking back-office")
    kestrel = Client(name="Kestrel IT Services", industry="IT services")
    db.add_all([meridian, kestrel])
    db.flush()
    recruiter = User(email="recruiter@companya.demo", full_name="Demo Recruiter", role=Role.recruiter, password_hash=pwd.hash("Demo@1234"))
    head = User(email="head@companya.demo", full_name="Demo Delivery Head", role=Role.delivery_head, password_hash=pwd.hash("Demo@1234"))
    priya = User(email="priya@meridianbank.demo", full_name="Priya Sharma", role=Role.client, client_id=meridian.id, password_hash=pwd.hash("Demo@1234"))
    rahul = User(email="rahul@kestrelit.demo", full_name="Rahul Mehta", role=Role.client, client_id=kestrel.id, password_hash=pwd.hash("Demo@1234"))
    db.add_all([recruiter, head, priya, rahul])
    db.flush()

    seeded_at = datetime.now(timezone.utc)
    requisitions = [
        Requisition(client_id=kestrel.id, owner_id=recruiter.id, title="Senior Java Developer", location="Noida", jd_text="Senior Java Developer, Noida, 5-8 years, Java, Spring Boot, Microservices, Kafka, AWS, notice 60 days or less, budget up to 28 LPA", openings=3, created_at=seeded_at - timedelta(days=2)),
        Requisition(client_id=meridian.id, owner_id=recruiter.id, title="KYC Analyst", location="Noida", jd_text="KYC Analyst, Noida, 2-5 years, KYC, AML, Excel, CDD, sanctions screening, notice 30 days or less", openings=2, created_at=seeded_at - timedelta(days=6)),
        Requisition(client_id=kestrel.id, owner_id=recruiter.id, title="React Frontend Developer", location="Gurugram", jd_text="React Frontend Developer, Gurugram, 3-6 years, React, TypeScript, JavaScript, accessibility, notice 45 days or less", openings=2, created_at=seeded_at - timedelta(days=11)),
    ]
    db.add_all(requisitions)
    db.flush()
    drafts = [
        {"title": req.title, "location": req.location, "experience": {}, "must_have_skills": [], "nice_to_have_skills": [], "ctc": {}, "notice": {}, "field_confidence": {}}
        for req in requisitions
    ]
    for req, kind, draft in zip(requisitions, ("java", "kyc", "react"), drafts):
        db.add(Scorecard(requisition_id=req.id, version=1, is_active=True, created_by=recruiter.id, criteria=_criteria(kind), ai_draft=draft, ai_confidence={}))
    db.commit()

    file_ids = []
    for req, kind in zip(requisitions, ("java", "kyc", "react")):
        paths = _files_for(kind)
        batch = UploadBatch(requisition_id=req.id, uploaded_by=recruiter.id, total=len(paths), processed=0, failed=0, duplicates=0, status="processing")
        db.add(batch)
        db.flush()
        for path in paths:
            data = path.read_bytes()
            row = CvFile(batch_id=batch.id, filename=path.name, mime="application/pdf" if path.suffix.lower() == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document", size_bytes=len(data), status="queued", attempts=0)
            db.add(row)
            db.flush()
            db.add(CvBlob(cv_file_id=row.id, data=data))
            file_ids.append((row.id, path.name))
    db.commit()
    db.close()

    original_mode = settings.ai_mode
    original_request_interval = settings.gemini_request_interval_seconds
    original_concurrency = settings.ai_concurrency
    try:
        if use_ai and original_mode == "gemini":
            settings.gemini_request_interval_seconds = REAL_AI_REQUEST_INTERVAL_SECONDS
            settings.ai_concurrency = 1
        asyncio.run(_process_files(file_ids, original_mode, use_ai))
    finally:
        settings.ai_mode = original_mode
        settings.gemini_request_interval_seconds = original_request_interval
        settings.ai_concurrency = original_concurrency

    db = SessionLocal()
    _record_demo_activity(db, recruiter, priya, rahul)
    db.commit()
    summary = _summary(db)
    db.close()
    print(f"Seed complete: {summary}")
    return summary


async def _process_files(file_ids: list[tuple[UUID, str]], configured_mode: str, use_ai: bool) -> None:
    for file_id, filename in file_ids:
        use_real_ai = use_ai and filename in REAL_AI_FILENAMES
        settings.ai_mode = configured_mode if use_real_ai else "mock"
        await process_file(file_id)
        if use_real_ai and _reset_rate_limited_file(file_id):
            print(f"Gemini remained rate limited for {filename}; retrying this file with mock AI.")
            settings.ai_mode = "mock"
            await process_file(file_id)
            _mark_mock_fallback(file_id)


def _reset_rate_limited_file(file_id: UUID) -> bool:
    db = SessionLocal()
    try:
        row = db.get(CvFile, file_id)
        if not row or row.status != "failed" or row.error_code != "ai_unavailable" or row.error_message != "AI busy — Retry":
            return False
        row.status = "queued"
        row.error_code = None
        row.error_message = None
        db.commit()
        return True
    finally:
        db.close()


def _mark_mock_fallback(file_id: UUID) -> None:
    db = SessionLocal()
    try:
        row = db.get(CvFile, file_id)
        if not row or row.status not in ("done", "needs_review") or not row.candidate_id:
            return
        batch = db.get(UploadBatch, row.batch_id)
        application = db.query(Application).filter_by(
            requisition_id=batch.requisition_id,
            candidate_id=row.candidate_id,
        ).first() if batch else None
        if application:
            score = db.query(Score).filter_by(application_id=application.id).order_by(Score.created_at.desc()).first()
            if score:
                score.model = "mock-fallback"
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Clear the database before seeding")
    parser.add_argument("--ai", action="store_true", help="Use the configured AI provider instead of deterministic mock mode")
    options = parser.parse_args()
    seed(reset=options.reset, use_ai=options.ai)
