from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Application, ClientFeedback, Role, StageEvent, User

PIPELINE_STAGES = (
    "sourced",
    "screened",
    "submitted",
    "shortlisted",
    "interview",
    "offered",
    "joined",
    "client_rejected",
    "withdrawn",
)
SYSTEM_TRANSITIONS = {"created": ("sourced",), "sourced": ("screened",)}

RECRUITER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "sourced": ("withdrawn",),
    "screened": ("submitted", "withdrawn"),
    "submitted": ("withdrawn",),
    "shortlisted": (),
    "interview": ("offered", "withdrawn"),
    "offered": ("joined", "withdrawn"),
    "joined": (),
    "client_rejected": (),
    "withdrawn": (),
}
CLIENT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "submitted": ("shortlisted", "client_rejected"),
    "shortlisted": (),
    "interview": (),
    "offered": (),
    "joined": (),
    "client_rejected": (),
    "sourced": (),
    "screened": (),
    "withdrawn": (),
}


def allowed_transitions(db: Session, application: Application, role: Role) -> list[str]:
    if role == Role.recruiter:
        targets = list(RECRUITER_TRANSITIONS.get(application.stage, ()))
        if application.stage != "withdrawn" and "withdrawn" not in targets:
            targets.append("withdrawn")
        if application.stage == "shortlisted":
            proposal = db.query(ClientFeedback).filter_by(application_id=application.id, action="propose_interview").order_by(ClientFeedback.created_at.desc()).first()
            if proposal and proposal.proposed_slots:
                targets.insert(0, "interview")
        return targets
    if role == Role.client:
        return list(CLIENT_TRANSITIONS.get(application.stage, ()))
    return []


def transition_application(
    db: Session,
    application: Application,
    target: str,
    actor: User,
    note: str | None = None,
    confirmed_slot: str | None = None,
    reason_code: str | None = None,
) -> Application:
    if target == "submitted" and not application.recruiter_opened_at:
        raise HTTPException(409, detail={"code": "cv_not_opened", "message": "Open the candidate CV before submitting to the client."})
    allowed = allowed_transitions(db, application, actor.role)
    if target not in allowed:
        raise HTTPException(
            422,
            detail={
                "code": "invalid_transition",
                "message": f"Cannot move application from {application.stage} to {target}.",
                "details": {"current_stage": application.stage, "allowed": allowed},
            },
        )
    if target == "withdrawn" and not (note or "").strip():
        raise HTTPException(422, detail={"code": "withdraw_note_required", "message": "Add a reason before withdrawing this candidate."})
    if target == "client_rejected" and not reason_code:
        raise HTTPException(422, detail={"code": "reason_required", "message": "Select a reason when rejecting a candidate."})
    if target == "interview":
        proposal = db.query(ClientFeedback).filter_by(application_id=application.id, action="propose_interview").order_by(ClientFeedback.created_at.desc()).first()
        slots = proposal.proposed_slots if proposal else []
        if not confirmed_slot or confirmed_slot not in (slots or []):
            raise HTTPException(422, detail={"code": "interview_slot_required", "message": "Confirm one of the interview slots proposed by the client.", "details": {"proposed_slots": slots or []}})
        try:
            selected = datetime.fromisoformat(confirmed_slot.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(422, detail={"code": "invalid_interview_slot", "message": "The selected interview slot is not a valid datetime."}) from exc
        if selected <= datetime.now(timezone.utc):
            raise HTTPException(422, detail={"code": "invalid_interview_slot", "message": "Choose a future interview slot."})
        note = f"Recruiter confirmed client-proposed slot: {confirmed_slot}"
    previous = application.stage
    application.stage = target
    if target == "submitted":
        application.submitted_at = datetime.now(timezone.utc)
        application.submitted_by = actor.id
        application.recruiter_note = note
    db.add(StageEvent(application_id=application.id, from_stage=previous, to_stage=target, actor_id=actor.id, note=note))
    return application


def transition_system(db: Session, application: Application, target: str, actor_id, note: str | None = None) -> Application:
    if target not in SYSTEM_TRANSITIONS.get(application.stage, ()):
        raise HTTPException(422, detail={"code": "invalid_transition", "message": f"System cannot move application from {application.stage} to {target}.", "details": {"current_stage": application.stage, "allowed": list(SYSTEM_TRANSITIONS.get(application.stage, ()))}})
    previous = application.stage
    application.stage = target
    db.add(StageEvent(application_id=application.id, from_stage=previous, to_stage=target, actor_id=actor_id, note=note))
    return application
