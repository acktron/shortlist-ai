from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..models import Application, AccessLog, Candidate, ClientFeedback, Requisition, Role, Score, Scorecard, User
from ..schemas.portal import PortalFeedback
from ..services.evidence import normalize_criteria_evidence
from ..services.pipeline import CLIENT_VISIBLE_STAGES, transition_application
from ..services.scoring import build_score_summary

router = APIRouter(prefix="/portal", tags=["portal"])


def _visible_application(db: Session, application_id: UUID, user: User) -> tuple[Application, Requisition, Candidate]:
    application = db.get(Application, application_id)
    requisition = db.get(Requisition, application.requisition_id) if application else None
    if not application or not requisition or requisition.client_id != user.client_id or application.submitted_at is None or application.stage not in CLIENT_VISIBLE_STAGES:
        raise HTTPException(404, "Candidate not found")
    candidate = db.get(Candidate, application.candidate_id)
    if not candidate or candidate.deleted_at:
        raise HTTPException(404, "Candidate not found")
    return application, requisition, candidate


def _masked_name(full_name: str | None) -> str:
    parts = (full_name or "Candidate").split()
    if len(parts) < 2:
        return parts[0] if parts else "Candidate"
    return f"{parts[0]} {parts[-1][0].upper()}."


def _score(db: Session, application: Application, requisition_id: UUID) -> Score | None:
    scorecard = db.query(Scorecard).filter_by(requisition_id=requisition_id, is_active=True).first()
    if not scorecard:
        return None
    return db.query(Score).filter_by(application_id=application.id, scorecard_id=scorecard.id).order_by(Score.created_at.desc()).first()


def _serialize(db: Session, application: Application, requisition: Requisition, candidate: Candidate, include_cv: bool) -> dict:
    score = _score(db, application, requisition.id)
    criteria = normalize_criteria_evidence(score.criteria, candidate.redacted_text or "") if score and isinstance(score.criteria, list) else []
    evidence = []
    for item in criteria:
        if item.get("verdict") not in ("met", "partial"):
            continue
        for quote in item.get("evidence", []):
            if quote.get("verified") and quote.get("quote"):
                evidence.append({"label": item.get("label", "Evidence"), "verdict": item.get("verdict"), "quote": quote["quote"]})
    result = {
        "application_id": str(application.id),
        "candidate_code": candidate.candidate_code,
        "name": _masked_name(candidate.full_name),
        "current_role": candidate.current_role,
        "experience_years": float(candidate.total_exp_years) if candidate.total_exp_years is not None else None,
        "skills": candidate.skills or [],
        "notice_days": candidate.notice_days,
        "expected_ctc_lpa": float(candidate.expected_ctc_lpa) if candidate.expected_ctc_lpa is not None else None,
        "score_summary": build_score_summary(score.total if score else None, score.band if score else None, criteria),
        "top_evidence": evidence[:4],
        "recruiter_note": application.recruiter_note,
        "status": application.stage,
        "band": score.band if score else None,
    }
    if include_cv:
        result["redacted_cv_text"] = candidate.redacted_text or ""
    return result


@router.get("/requisitions")
def requisitions(db: Session = Depends(get_db), user: User = Depends(require_role(Role.client))):
    rows = db.query(Requisition).filter_by(client_id=user.client_id, status="open").order_by(Requisition.created_at.desc()).all()
    result = []
    for requisition in rows:
        count = db.query(Application).filter(Application.requisition_id == requisition.id, Application.submitted_at.is_not(None), Application.stage.in_(CLIENT_VISIBLE_STAGES)).count()
        if count:
            result.append({"id": str(requisition.id), "title": requisition.title, "location": requisition.location, "candidate_count": count})
    return result


@router.get("/requisitions/{requisition_id}/candidates")
def candidates(
    requisition_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.client)),
):
    requisition = db.get(Requisition, requisition_id)
    if not requisition or requisition.client_id != user.client_id:
        raise HTTPException(404, "Requisition not found")
    applications = db.query(Application).filter(Application.requisition_id == requisition.id, Application.submitted_at.is_not(None), Application.stage.in_(CLIENT_VISIBLE_STAGES)).order_by(Application.submitted_at.desc()).all()
    result = []
    for application in applications:
        candidate = db.get(Candidate, application.candidate_id)
        if not candidate or candidate.deleted_at:
            continue
        db.add(AccessLog(user_id=user.id, candidate_id=candidate.id, action="view_portal_profile"))
        result.append(_serialize(db, application, requisition, candidate, include_cv=False))
    db.commit()
    return result


@router.get("/applications/{application_id}")
def application_detail(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.client)),
):
    application, requisition, candidate = _visible_application(db, application_id, user)
    db.add(AccessLog(user_id=user.id, candidate_id=candidate.id, action="view_portal_profile"))
    result = _serialize(db, application, requisition, candidate, include_cv=True)
    db.commit()
    return result


@router.post("/applications/{application_id}/feedback")
def feedback(
    application_id: UUID,
    data: PortalFeedback,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.client)),
):
    application, _requisition, candidate = _visible_application(db, application_id, user)
    now = datetime.now(timezone.utc)
    if data.action == "reject":
        if not data.reason_code:
            raise HTTPException(422, detail={"code": "reason_required", "message": "Select a reason when rejecting a candidate."})
        if data.reason_code == "other" and not (data.note or "").strip():
            raise HTTPException(422, detail={"code": "note_required", "message": "Add a note when choosing other."})
        transition_application(db, application, "client_rejected", user, note=data.note, reason_code=data.reason_code)
    elif data.action == "shortlist":
        transition_application(db, application, "shortlisted", user, note=data.note)
    elif data.action == "propose_interview":
        if application.stage != "shortlisted":
            raise HTTPException(422, detail={"code": "invalid_transition", "message": "Shortlist this candidate before proposing an interview."})
        if not 1 <= len(data.proposed_slots) <= 3:
            raise HTTPException(422, detail={"code": "slots_required", "message": "Propose between one and three interview slots."})
        normalized_slots = []
        for slot in data.proposed_slots:
            if slot.tzinfo is None or slot <= now:
                raise HTTPException(422, detail={"code": "invalid_interview_slot", "message": "Interview slots must be future datetimes with a timezone."})
            normalized_slots.append(slot.astimezone(timezone.utc).isoformat())
        if len(set(normalized_slots)) != len(normalized_slots):
            raise HTTPException(422, detail={"code": "duplicate_interview_slot", "message": "Interview slots must be different."})
        data.proposed_slots = [datetime.fromisoformat(slot) for slot in normalized_slots]
    db.add(ClientFeedback(application_id=application.id, client_user_id=user.id, action=data.action, reason_code=data.reason_code, note=data.note, proposed_slots=[slot.astimezone(timezone.utc).isoformat() for slot in data.proposed_slots] if data.action == "propose_interview" else None))
    db.add(AccessLog(user_id=user.id, candidate_id=candidate.id, action="view_portal_profile"))
    db.commit()
    return {"application_id": str(application.id), "action": data.action, "status": application.stage}
