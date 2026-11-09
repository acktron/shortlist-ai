from datetime import date, datetime, time, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..models import Application, Candidate, Client, Requisition, Role, Score, Scorecard, User
from ..services.scoring import build_score_summary

router = APIRouter(tags=["insights"])
ACCEPTED_STAGES = {"shortlisted", "interview", "offered", "joined"}


def _week_range(value: str | None) -> tuple[str, datetime, datetime]:
    current = datetime.now(timezone.utc).isocalendar()
    label = value or f"{current.year}-W{current.week:02d}"
    try:
        year_text, week_text = label.split("-W", maxsplit=1)
        monday = date.fromisocalendar(int(year_text), int(week_text), 1)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, detail={"code": "invalid_week", "message": "Week must use ISO format YYYY-Www."}) from exc
    start = datetime.combine(monday, time.min, tzinfo=timezone.utc)
    return label, start, start + timedelta(days=7)


def _in_week(value: datetime | None, start: datetime, end: datetime) -> bool:
    if value is None:
        return False
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return start <= normalized < end


def _latest_score(db: Session, application: Application, scorecard: Scorecard | None) -> Score | None:
    if not scorecard:
        return None
    return db.query(Score).filter_by(application_id=application.id, scorecard_id=scorecard.id).order_by(Score.created_at.desc()).first()


def _rank_item(candidate: Candidate, application: Application, score: Score | None) -> dict:
    criteria = score.criteria if score and isinstance(score.criteria, list) else []
    return {
        "candidate_id": str(candidate.id),
        "candidate_code": candidate.candidate_code,
        "name": candidate.full_name,
        "current_role": candidate.current_role,
        "score": score.total if score else None,
        "coverage": float(score.coverage) if score and score.coverage is not None else 0,
        "band": score.band if score else None,
        "score_summary": build_score_summary(score.total if score else None, score.band if score else None, criteria),
        "needs_review": bool(score and score.needs_review),
        "stage": application.stage,
        "must_have_met": sum(item.get("kind") == "must_skill" and item.get("verdict") == "met" for item in criteria),
    }


@router.get("/insights/calibration")
def calibration(
    week: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.delivery_head)),
):
    label, start, end = _week_range(week)
    requisitions = db.query(Requisition).order_by(Requisition.title).all()
    result = []
    for requisition in requisitions:
        applications = db.query(Application).filter_by(requisition_id=requisition.id).all()
        submitted = [application for application in applications if _in_week(application.submitted_at, start, end)]
        if not submitted:
            continue
        scorecard = db.query(Scorecard).filter_by(requisition_id=requisition.id, is_active=True).first()
        scored = []
        review_count = 0
        for application in applications:
            candidate = db.get(Candidate, application.candidate_id)
            if not candidate or candidate.deleted_at:
                continue
            score = _latest_score(db, application, scorecard)
            if score and score.needs_review:
                review_count += 1
            scored.append(_rank_item(candidate, application, score))
        scored.sort(key=lambda item: (-(item["score"] if item["score"] is not None else -1), -item["coverage"], -item["must_have_met"], item["candidate_code"] or ""))
        count = len(submitted)
        submitted_ids = {str(application.candidate_id) for application in submitted}
        top_n = scored[:count]
        top_ids = {item["candidate_id"] for item in top_n}
        overlap = len(submitted_ids & top_ids)
        item_by_id = {item["candidate_id"]: item for item in scored}
        low_submissions = [item_by_id.get(str(application.candidate_id)) for application in submitted if str(application.candidate_id) not in top_ids]
        high_not_submitted = [item for item in top_n if item["candidate_id"] not in submitted_ids]
        accepted = sum(application.stage in ACCEPTED_STAGES for application in submitted)
        overrides = sum(bool(item and item["stage"] in ACCEPTED_STAGES) for item in low_submissions)
        result.append({
            "requisition_id": str(requisition.id),
            "title": requisition.title,
            "client_name": db.get(Client, requisition.client_id).name,
            "submitted_count": count,
            "top_n": count,
            "overlap_percent": round(100 * overlap / count) if count else 0,
            "submitted_but_ranked_low": [item for item in low_submissions if item],
            "ranked_high_not_submitted": high_not_submitted,
            "client_acceptance_rate": round(100 * accepted / count) if count else 0,
            "needs_review_count": review_count,
            "overrides": overrides,
        })
    return {"week": label, "requisitions": result}
