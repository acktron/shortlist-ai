from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import AccessLog, Application, Candidate, ClientFeedback, Requisition, StageEvent, User
from app.services.pipeline import allowed_transitions


def _token(client, email="recruiter@companya.demo"):
    response = client.post("/api/auth/login", json={"email": email, "password": "Demo@1234"})
    return response.json()["access_token"]


def test_submit_requires_cv_opened(client):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    db = SessionLocal()
    requisition = db.query(Requisition).first()
    candidate = Candidate(candidate_code="CND-SUBMIT", full_name="Submit Candidate", raw_text="CV", redacted_text="CV", skills=[], consent_status="pending")
    db.add(candidate)
    db.flush()
    from app.models import CvBlob, CvFile, UploadBatch
    batch = UploadBatch(requisition_id=requisition.id, uploaded_by=requisition.owner_id, total=1, processed=1, failed=0, duplicates=0, status="done")
    db.add(batch)
    db.flush()
    file = CvFile(batch_id=batch.id, candidate_id=candidate.id, filename="submit.pdf", mime="application/pdf", size_bytes=4, status="done")
    db.add(file)
    db.flush()
    db.add(CvBlob(cv_file_id=file.id, data=b"%PDF"))
    application = Application(requisition_id=requisition.id, candidate_id=candidate.id, cv_file_id=file.id, stage="sourced")
    db.add(application)
    db.commit()
    response = client.post(f"/api/applications/{application.id}/submit", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cv_not_opened"
    db.close()


def test_opening_cv_moves_to_screened_and_logs_access(client):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    db = SessionLocal()
    requisition = db.query(Requisition).first()
    candidate = Candidate(candidate_code="CND-OPEN", full_name="Open Candidate", raw_text="Java CV", redacted_text="Java CV", skills=[], consent_status="pending")
    db.add(candidate)
    db.flush()
    from app.models import CvBlob, CvFile, UploadBatch
    batch = UploadBatch(requisition_id=requisition.id, uploaded_by=requisition.owner_id, total=1, processed=1, failed=0, duplicates=0, status="done")
    db.add(batch)
    db.flush()
    file = CvFile(batch_id=batch.id, candidate_id=candidate.id, filename="open.pdf", mime="application/pdf", size_bytes=4, status="done")
    db.add(file)
    db.flush()
    db.add(CvBlob(cv_file_id=file.id, data=b"%PDF"))
    application = Application(requisition_id=requisition.id, candidate_id=candidate.id, cv_file_id=file.id, stage="sourced")
    db.add(application)
    db.commit()
    application_id = application.id
    db.close()

    response = client.get(f"/api/applications/{application_id}/cv", headers=headers)
    assert response.status_code == 200
    db = client.db_session
    assert db.get(Application, application_id).stage == "screened"
    assert db.query(StageEvent).filter_by(application_id=application_id, from_stage="sourced", to_stage="screened").count() == 1
    assert db.query(AccessLog).filter_by(candidate_id=candidate.id, action="view_cv").count() == 1


def test_invalid_transition_returns_allowed_stage_list(client):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    with SessionLocal() as db:
        application = db.query(Application).filter_by(stage="submitted").first()
        application_id = application.id
    response = client.post(f"/api/applications/{application_id}/stage", headers=headers, json={"stage": "joined"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_transition"
    assert error["details"]["current_stage"] == "submitted"
    assert "withdrawn" in error["details"]["allowed"]


def test_recruiter_cannot_set_client_rejected_stage(client):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    with SessionLocal() as db:
        application = db.query(Application).filter_by(stage="submitted").first()
        application_id = application.id
    response = client.post(f"/api/applications/{application_id}/stage", headers=headers, json={"stage": "client_rejected"})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["allowed"] == ["withdrawn"]


def test_recruiter_confirms_one_client_proposed_slot(client):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    db = SessionLocal()
    requisition = db.query(Requisition).first()
    recruiter = db.query(User).filter_by(email="recruiter@companya.demo").one()
    client_user = db.query(User).filter_by(email="priya@meridianbank.demo").one()
    candidate = Candidate(candidate_code="CND-INTERVIEW", full_name="Interview Candidate", raw_text="CV", redacted_text="CV", skills=[], consent_status="pending")
    db.add(candidate)
    db.flush()
    from app.models import CvBlob, CvFile, UploadBatch
    batch = UploadBatch(requisition_id=requisition.id, uploaded_by=recruiter.id, total=1, processed=1, failed=0, duplicates=0, status="done")
    db.add(batch)
    db.flush()
    file = CvFile(batch_id=batch.id, candidate_id=candidate.id, filename="interview.pdf", mime="application/pdf", size_bytes=4, status="done")
    db.add(file)
    db.flush()
    db.add(CvBlob(cv_file_id=file.id, data=b"%PDF"))
    application = Application(requisition_id=requisition.id, candidate_id=candidate.id, cv_file_id=file.id, stage="shortlisted")
    db.add(application)
    db.flush()
    slots = [(datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(), (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=14, minute=0, second=0, microsecond=0).isoformat()]
    db.add(ClientFeedback(application_id=application.id, client_user_id=client_user.id, action="propose_interview", proposed_slots=slots))
    db.commit()
    application_id = application.id
    db.close()

    with SessionLocal() as db:
        assert allowed_transitions(db, db.get(Application, application_id), recruiter.role) == ["interview", "withdrawn"]
    invalid = client.post(f"/api/applications/{application_id}/stage", headers=headers, json={"stage": "interview", "confirmed_slot": "2030-01-01T10:00:00+00:00"})
    assert invalid.status_code == 422
    valid = client.post(f"/api/applications/{application_id}/stage", headers=headers, json={"stage": "interview", "confirmed_slot": slots[0]})
    assert valid.status_code == 200
    assert valid.json()["stage"] == "interview"
    event = client.db_session.query(StageEvent).filter_by(application_id=application_id, to_stage="interview").one()
    assert slots[0] in event.note


def test_pipeline_groups_cards_and_includes_empty_columns(client):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    requisition = client.get("/api/requisitions", headers=headers).json()[0]
    response = client.get(f"/api/requisitions/{requisition['id']}/pipeline", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert [column["stage"] for column in data["columns"]] == ["sourced", "screened", "submitted", "shortlisted", "interview", "offered", "joined", "client_rejected", "withdrawn"]
    assert sum(column["count"] for column in data["columns"]) == data["total"]


def test_stage_entered_at_uses_latest_event_in_pipeline_and_application_responses(client):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    with SessionLocal() as db:
        application = db.query(Application).first()
        recruiter = db.query(User).filter_by(email="recruiter@companya.demo").one()
        requisition_id = application.requisition_id
        application_id = application.id
        previous = db.query(StageEvent).filter_by(application_id=application_id).order_by(StageEvent.created_at.desc()).first()
        previous_at = previous.created_at if previous else datetime.now(timezone.utc)
        if previous_at.tzinfo is None:
            previous_at = previous_at.replace(tzinfo=timezone.utc)
        expected = (max(datetime.now(timezone.utc), previous_at) + timedelta(seconds=1)).replace(microsecond=0)
        db.add(StageEvent(
            application_id=application_id,
            from_stage="test_previous",
            to_stage=application.stage,
            actor_id=recruiter.id,
            note="stage timestamp test",
            created_at=expected,
        ))
        db.commit()

    pipeline = client.get(f"/api/requisitions/{requisition_id}/pipeline", headers=headers).json()
    item = next(card for column in pipeline["columns"] for card in column["applications"] if card["id"] == str(application_id))
    detail = client.get(f"/api/applications/{application_id}", headers=headers).json()
    listed = client.get(f"/api/requisitions/{requisition_id}/applications", headers=headers).json()
    listed_item = next(row for row in listed["items"] if row["id"] == str(application_id))

    for payload in (item, detail, listed_item):
        actual = datetime.fromisoformat(payload["stage_entered_at"])
        assert actual.replace(tzinfo=None) == expected.replace(tzinfo=None)
