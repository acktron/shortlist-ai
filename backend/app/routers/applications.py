from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..models import (
    AccessLog,
    Application,
    Candidate,
    ClientFeedback,
    CvBlob,
    CvFile,
    DeletionRequest,
    Role,
    Score,
    StageEvent,
    User,
)
from fastapi import Response

router = APIRouter(tags=["applications"])


class SubmitRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class WithdrawRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


def _application(db: Session, application_id: UUID) -> Application:
    row = db.get(Application, application_id)
    if not row:
        raise HTTPException(404, "Application not found")
    return row


def _candidate(db: Session, candidate_id: UUID) -> Candidate:
    row = db.get(Candidate, candidate_id)
    if not row:
        raise HTTPException(404, "Candidate not found")
    return row


def _latest_score(db: Session, application_id: UUID) -> Score | None:
    return db.query(Score).filter_by(application_id=application_id).order_by(Score.created_at.desc()).first()


@router.get("/applications/{application_id}")
def detail(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.recruiter, Role.delivery_head)),
):
    row = _application(db, application_id)
    candidate = _candidate(db, row.candidate_id)
    score = _latest_score(db, row.id)
    duplicate = db.get(Candidate, candidate.duplicate_of_id) if candidate.duplicate_of_id else None
    db.add(AccessLog(user_id=user.id, candidate_id=candidate.id, action="view_profile"))
    db.commit()
    return {
        "id": str(row.id),
        "candidate_id": str(candidate.id),
        "candidate_code": candidate.candidate_code,
        "name": candidate.full_name,
        "current_role": candidate.current_role,
        "experience": float(candidate.total_exp_years) if candidate.total_exp_years is not None else None,
        "skills": candidate.skills or [],
        "notice_days": candidate.notice_days,
        "stage": row.stage,
        "recruiter_note": row.recruiter_note,
        "recruiter_opened_at": row.recruiter_opened_at,
        "raw_text": candidate.raw_text,
        "redacted_text": candidate.redacted_text,
        "scoring_input": score.scoring_input if score else None,
        "criteria": score.criteria if score else [],
        "score": score.total if score else None,
        "band": score.band if score else None,
        "needs_review": bool(score and score.needs_review),
        "review_reasons": score.review_reasons if score else [],
        "consent_status": candidate.consent_status,
        "duplicate_of": ({"id": str(duplicate.id), "candidate_code": duplicate.candidate_code, "name": duplicate.full_name} if duplicate else None),
    }


@router.get("/applications/{application_id}/cv")
def cv(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.recruiter, Role.delivery_head)),
):
    row = _application(db, application_id)
    blob = db.query(CvBlob).filter_by(cv_file_id=row.cv_file_id).first()
    if not blob:
        raise HTTPException(404, "CV not found")
    if row.recruiter_opened_at is None:
        row.recruiter_opened_at = datetime.now(timezone.utc)
        if row.stage == "sourced":
            previous = row.stage
            row.stage = "screened"
            db.add(StageEvent(application_id=row.id, from_stage=previous, to_stage="screened", actor_id=user.id, note="Recruiter opened CV"))
    db.add(AccessLog(user_id=user.id, candidate_id=row.candidate_id, action="view_cv"))
    db.commit()
    file = db.get(CvFile, row.cv_file_id)
    return Response(content=blob.data, media_type=file.mime if file else "application/octet-stream")


@router.post("/applications/{application_id}/submit")
def submit(
    application_id: UUID,
    data: SubmitRequest = Body(default=SubmitRequest()),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.recruiter)),
):
    row = _application(db, application_id)
    if not row.recruiter_opened_at:
        raise HTTPException(409, detail={"code": "cv_not_opened", "message": "Open the candidate CV before submitting to the client."})
    if row.stage not in ("sourced", "screened"):
        raise HTTPException(422, detail={"code": "invalid_transition", "message": "Only sourced or screened candidates can be submitted."})
    previous = row.stage
    row.stage = "submitted"
    row.submitted_at = datetime.now(timezone.utc)
    row.submitted_by = user.id
    row.recruiter_note = data.note
    db.add(StageEvent(application_id=row.id, from_stage=previous, to_stage="submitted", actor_id=user.id, note=data.note))
    db.commit()
    return {"id": str(row.id), "stage": row.stage}


@router.post("/applications/{application_id}/withdraw")
def withdraw(
    application_id: UUID,
    data: WithdrawRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.recruiter)),
):
    row = _application(db, application_id)
    previous = row.stage
    row.stage = "withdrawn"
    db.add(StageEvent(application_id=row.id, from_stage=previous, to_stage="withdrawn", actor_id=user.id, note=data.note))
    db.commit()
    return {"id": str(row.id), "stage": row.stage}


@router.post("/candidates/{candidate_id}/merge")
def merge_duplicate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.recruiter)),
):
    duplicate = _candidate(db, candidate_id)
    if not duplicate.duplicate_of_id:
        raise HTTPException(409, detail={"code": "not_a_possible_duplicate", "message": "This candidate has no possible duplicate to merge."})
    original = _candidate(db, duplicate.duplicate_of_id)
    duplicate_apps = db.query(Application).filter_by(candidate_id=duplicate.id).all()
    for duplicate_app in duplicate_apps:
        original_app = db.query(Application).filter_by(requisition_id=duplicate_app.requisition_id, candidate_id=original.id).first()
        if original_app:
            for score in db.query(Score).filter_by(application_id=duplicate_app.id).all():
                db.delete(score)
            for event in db.query(StageEvent).filter_by(application_id=duplicate_app.id).all():
                event.application_id = original_app.id
            for feedback in db.query(ClientFeedback).filter_by(application_id=duplicate_app.id).all():
                feedback.application_id = original_app.id
            for file in db.query(CvFile).filter_by(candidate_id=duplicate.id).all():
                if file.id == duplicate_app.cv_file_id:
                    file.candidate_id = original.id
            db.delete(duplicate_app)
        else:
            duplicate_app.candidate_id = original.id
    for file in db.query(CvFile).filter_by(candidate_id=duplicate.id).all():
        file.candidate_id = original.id
    for log in db.query(AccessLog).filter_by(candidate_id=duplicate.id).all():
        log.candidate_id = original.id
    for request in db.query(DeletionRequest).filter_by(candidate_id=duplicate.id).all():
        request.candidate_id = original.id
    db.query(Candidate).filter_by(duplicate_of_id=duplicate.id).update({Candidate.duplicate_of_id: original.id})
    db.delete(duplicate)
    db.commit()
    return {"merged": True, "candidate_id": str(original.id), "candidate_code": original.candidate_code}


@router.post("/candidates/{candidate_id}/not-duplicate")
def mark_not_duplicate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.recruiter)),
):
    candidate = _candidate(db, candidate_id)
    if not candidate.duplicate_of_id:
        raise HTTPException(409, detail={"code": "not_a_possible_duplicate", "message": "This candidate has no possible duplicate to clear."})
    candidate.duplicate_of_id = None
    if candidate.parse_confidence != "low":
        db.query(CvFile).filter_by(candidate_id=candidate.id, status="needs_review").update({CvFile.status: "done"})
    db.commit()
    return {"candidate_id": str(candidate.id), "duplicate": False}
