from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..models import Application, Candidate, ClientFeedback, Requisition, Role, Score, Scorecard, User
from ..services.pipeline import PIPELINE_STAGES, allowed_transitions, stage_entered_at
from ..services.scoring import build_score_summary

router = APIRouter(tags=["pipeline"])


@router.get("/requisitions/{requisition_id}/pipeline")
def get_pipeline(
    requisition_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.recruiter, Role.delivery_head)),
):
    requisition = db.get(Requisition, requisition_id)
    if not requisition:
        raise HTTPException(404, "Requisition not found")
    scorecard = db.query(Scorecard).filter_by(requisition_id=requisition_id, is_active=True).first()
    columns = {stage: [] for stage in PIPELINE_STAGES}
    applications = db.query(Application).filter_by(requisition_id=requisition_id).all()
    for application in applications:
        candidate = db.get(Candidate, application.candidate_id)
        score = db.query(Score).filter_by(application_id=application.id, scorecard_id=scorecard.id).order_by(Score.created_at.desc()).first() if scorecard else None
        proposal = db.query(ClientFeedback).filter_by(application_id=application.id, action="propose_interview").order_by(ClientFeedback.created_at.desc()).first()
        columns.setdefault(application.stage, []).append({
            "id": str(application.id),
            "candidate_id": str(candidate.id),
            "candidate_code": candidate.candidate_code,
            "name": candidate.full_name,
            "current_role": candidate.current_role,
            "experience": float(candidate.total_exp_years) if candidate.total_exp_years is not None else None,
            "score": score.total if score else None,
            "band": score.band if score else None,
            "score_summary": build_score_summary(score.total if score else None, score.band if score else None, score.criteria or [] if score else []),
            "needs_review": bool(score and score.needs_review),
            "stage_entered_at": stage_entered_at(db, application),
            "recruiter_opened_at": application.recruiter_opened_at,
            "allowed_transitions": allowed_transitions(db, application, user.role),
            "proposed_slots": proposal.proposed_slots if proposal else [],
        })
    return {
        "requisition_id": str(requisition.id),
        "columns": [{"stage": stage, "count": len(columns[stage]), "applications": columns[stage]} for stage in PIPELINE_STAGES],
        "total": len(applications),
    }
