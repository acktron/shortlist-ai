from app.models import AccessLog, Application, Candidate, CvBlob, CvFile, DeletionRequest, Requisition, Score, Scorecard, StageEvent, UploadBatch, User


def _token(client, email):
    response = client.post("/api/auth/login", json={"email": email, "password": "Demo@1234"})
    return response.json()["access_token"]


def test_delivery_head_calibration_and_role_access(client):
    head = {"Authorization": f"Bearer {_token(client, 'head@companya.demo')}"}
    recruiter = {"Authorization": f"Bearer {_token(client, 'recruiter@companya.demo')}"}
    client_user = {"Authorization": f"Bearer {_token(client, 'priya@meridianbank.demo')}"}
    response = client.get("/api/insights/calibration", headers=head)
    assert response.status_code == 200
    assert response.json()["requisitions"]
    assert response.json()["requisitions"][0]["submitted_count"] >= 1
    assert client.get("/api/insights/calibration?week=not-a-week", headers=head).status_code == 422
    assert client.get("/api/insights/calibration", headers=recruiter).status_code == 403
    assert client.get("/api/insights/calibration", headers=client_user).status_code == 403


def test_delivery_head_can_view_candidate_access_log(client):
    db = client.db_session
    candidate = db.query(Candidate).filter_by(candidate_code="CND-SMOKE").one()
    recruiter = db.query(User).filter_by(email="recruiter@companya.demo").one()
    db.add(AccessLog(user_id=recruiter.id, candidate_id=candidate.id, action="view_profile", ip="127.0.0.1", user_agent="test"))
    db.flush()
    head = {"Authorization": f"Bearer {_token(client, 'head@companya.demo')}"}
    recruiter_headers = {"Authorization": f"Bearer {_token(client, 'recruiter@companya.demo')}"}
    response = client.get(f"/api/candidates/{candidate.id}/access-log", headers=head)
    assert response.status_code == 200
    assert response.json()["events"][0]["action"] == "view_profile"
    assert client.get(f"/api/candidates/{candidate.id}/access-log", headers=recruiter_headers).status_code == 403


def test_deletion_anonymizes_candidate_and_removes_cv_blobs(client):
    db = client.db_session
    recruiter = db.query(User).filter_by(email="recruiter@companya.demo").one()
    requisition = db.query(Requisition).filter_by(title="Senior Java Developer").one()
    scorecard = db.query(Scorecard).filter_by(requisition_id=requisition.id, is_active=True).one()
    batch = db.query(UploadBatch).filter_by(requisition_id=requisition.id).first()
    candidate = Candidate(candidate_code="CND-DELETE", full_name="Maya Identifiable", email="maya.private@example.demo", phone="+91 9876543210", current_role="Java Developer", total_exp_years=6, skills=["Java"], notice_days=30, location="Noida", raw_text="Maya Identifiable\nEmail: maya.private@example.demo\nPhone: +91 9876543210", redacted_text="Java Developer", education=[{"school": "Private Institute"}], experience=[{"company": "Private Company"}], consent_status="granted")
    db.add(candidate)
    db.flush()
    file = CvFile(batch_id=batch.id, candidate_id=candidate.id, filename="Maya Identifiable CV.pdf", mime="application/pdf", size_bytes=100, status="done")
    db.add(file)
    db.flush()
    db.add(CvBlob(cv_file_id=file.id, data=b"%PDF private CV"))
    application = Application(requisition_id=requisition.id, candidate_id=candidate.id, cv_file_id=file.id, stage="sourced", recruiter_note="Maya can start soon.")
    db.add(application)
    db.flush()
    event = StageEvent(application_id=application.id, from_stage="created", to_stage="sourced", actor_id=recruiter.id, note="Maya Identifiable added")
    db.add(event)
    db.add(Score(application_id=application.id, scorecard_id=scorecard.id, total=50, coverage=1, band="possible", confidence="medium", needs_review=False, review_reasons=[], criteria=[], scoring_input="<cv>Java Developer</cv>", model="mock", prompt_version="test", latency_ms=0))
    db.flush()
    candidate_id = candidate.id
    file_id = file.id
    application_id = application.id
    headers = {"Authorization": f"Bearer {_token(client, 'recruiter@companya.demo')}"}

    response = client.post(f"/api/candidates/{candidate_id}/deletion", headers=headers, json={})
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    db.refresh(candidate)
    db.refresh(event)
    db.refresh(file)
    assert candidate.full_name == "Deleted candidate"
    assert candidate.email is None and candidate.phone is None
    assert candidate.raw_text == "" and candidate.redacted_text == ""
    assert candidate.deleted_at is not None and candidate.consent_status == "withdrawn"
    assert "Maya" not in file.filename
    assert db.query(CvBlob).filter_by(cv_file_id=file_id).count() == 0
    assert db.query(Score).filter_by(application_id=application_id).count() == 0
    assert event.to_stage == "sourced" and event.note == "Anonymized following a deletion request."
    assert db.query(DeletionRequest).filter_by(candidate_id=candidate_id, status="completed").count() == 1
    assert client.get(f"/api/applications/{application_id}/cv", headers=headers).status_code == 404
