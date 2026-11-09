from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..models import AccessLog, Application, Candidate, ClientFeedback, CvBlob, CvFile, DeletionRequest, Role, Score, StageEvent, User

router = APIRouter(tags=["compliance"])


@router.get("/candidates/{candidate_id}/access-log")
def access_log(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.delivery_head)),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    events = db.query(AccessLog).filter_by(candidate_id=candidate_id).order_by(AccessLog.created_at.desc()).all()
    return {
        "candidate_code": candidate.candidate_code,
        "deleted": candidate.deleted_at is not None,
        "events": [
            {
                "action": event.action,
                "created_at": event.created_at,
                "user": db.get(User, event.user_id).full_name if event.user_id and db.get(User, event.user_id) else "Unknown user",
                "role": db.get(User, event.user_id).role.value if event.user_id and db.get(User, event.user_id) else None,
                "ip": event.ip,
                "user_agent": event.user_agent,
            }
            for event in events
        ],
    }


@router.post("/candidates/{candidate_id}/deletion")
def delete_candidate_data(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.recruiter)),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    completed_at = candidate.deleted_at or datetime.now(timezone.utc)
    candidate.full_name = "Deleted candidate"
    candidate.email = None
    candidate.phone = None
    candidate.current_role = None
    candidate.total_exp_years = None
    candidate.skills = []
    candidate.notice_days = None
    candidate.current_ctc_lpa = None
    candidate.expected_ctc_lpa = None
    candidate.location = None
    candidate.education = []
    candidate.experience = []
    candidate.raw_text = ""
    candidate.redacted_text = ""
    candidate.consent_status = "withdrawn"
    candidate.consent_source = None
    candidate.consent_at = None
    candidate.deleted_at = completed_at
    db.query(Candidate).filter_by(duplicate_of_id=candidate.id).update({Candidate.duplicate_of_id: None})

    applications = db.query(Application).filter_by(candidate_id=candidate.id).all()
    application_ids = [application.id for application in applications]
    for application in applications:
        application.recruiter_note = "Anonymized following a deletion request."
    db.query(StageEvent).filter(StageEvent.application_id.in_(application_ids)).update({StageEvent.note: "Anonymized following a deletion request."}, synchronize_session=False) if application_ids else None
    db.query(ClientFeedback).filter(ClientFeedback.application_id.in_(application_ids)).update({ClientFeedback.note: None, ClientFeedback.proposed_slots: None}, synchronize_session=False) if application_ids else None
    if application_ids:
        db.query(Score).filter(Score.application_id.in_(application_ids)).delete(synchronize_session=False)

    files = db.query(CvFile).filter_by(candidate_id=candidate.id).all()
    for file in files:
        db.query(CvBlob).filter_by(cv_file_id=file.id).delete(synchronize_session=False)
        file.filename = f"deleted-{file.id.hex[:12]}.pdf"
        file.error_message = None
        file.error_code = None
        file.status = "done"

    request = db.query(DeletionRequest).filter_by(candidate_id=candidate.id).first()
    if request:
        request.requested_by = user.id
        request.status = "completed"
        request.completed_at = completed_at
    else:
        db.add(DeletionRequest(candidate_id=candidate.id, requested_by=user.id, status="completed", completed_at=completed_at))
    db.commit()
    return {"candidate_id": str(candidate.id), "candidate_code": candidate.candidate_code, "deleted": True, "completed_at": completed_at}
