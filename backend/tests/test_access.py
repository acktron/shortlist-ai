from datetime import datetime, timedelta, timezone

from app.models import AccessLog, Application, Candidate, Client, ClientFeedback, CvFile, Requisition, Score, Scorecard, StageEvent, UploadBatch, User
from app.services.pipeline import allowed_transitions


def _headers(client, email="priya@meridianbank.demo"):
    response = client.post("/api/auth/login", json={"email": email, "password": "Demo@1234"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _portal_application(db, candidate_code, stage="submitted"):
    client_company = db.query(Client).filter_by(name="Meridian Bank").one()
    recruiter = db.query(User).filter_by(email="recruiter@companya.demo").one()
    scorecard = None
    requisition = db.query(Requisition).filter_by(title="KYC Analyst").first()
    if not requisition:
        requisition = Requisition(client_id=client_company.id, owner_id=recruiter.id, title="KYC Analyst", location="Noida", jd_text="KYC Analyst, Noida, 2-5 years, KYC, AML and Excel", openings=1, status="open")
        db.add(requisition)
        db.flush()
        scorecard = Scorecard(requisition_id=requisition.id, version=1, is_active=True, created_by=recruiter.id, criteria=[{"id": "kyc", "kind": "must_skill", "label": "KYC", "weight": 3, "params": {}}])
        db.add(scorecard)
        db.flush()
    else:
        scorecard = db.query(Scorecard).filter_by(requisition_id=requisition.id, is_active=True).first()
    candidate = Candidate(candidate_code=candidate_code, full_name="Maya Reddy", email=f"{candidate_code.lower()}@example.demo", phone="+91 9876543210", current_role="KYC Analyst", total_exp_years=3, skills=["KYC", "AML", "Excel"], notice_days=30, expected_ctc_lpa=12, location="Noida", raw_text="Maya Reddy\nEmail: private@example.demo\nPhone: +91 9876543210\nKYC Analyst\nKYC, AML, Excel\nExperience: 3 years", redacted_text="KYC Analyst\nKYC, AML, Excel\nExperience: 3 years", consent_status="granted")
    db.add(candidate)
    db.flush()
    batch = UploadBatch(requisition_id=requisition.id, uploaded_by=recruiter.id, total=1, processed=1, failed=0, duplicates=0, status="done")
    db.add(batch)
    db.flush()
    file = CvFile(batch_id=batch.id, candidate_id=candidate.id, filename=f"{candidate_code}.pdf", mime="application/pdf", size_bytes=100, status="done")
    db.add(file)
    db.flush()
    submitted_at = datetime.now(timezone.utc) if stage in {"submitted", "shortlisted", "interview", "offered", "joined", "client_rejected"} else None
    application = Application(requisition_id=requisition.id, candidate_id=candidate.id, cv_file_id=file.id, stage=stage, recruiter_opened_at=datetime.now(timezone.utc) if submitted_at else None, submitted_at=submitted_at, submitted_by=recruiter.id if submitted_at else None, recruiter_note="Recruiter note visible to the hiring manager.")
    db.add(application)
    db.flush()
    db.add(Score(application_id=application.id, scorecard_id=scorecard.id, total=80, coverage=1, band="strong", confidence="high", needs_review=False, review_reasons=[], criteria=[{"criterion_id": "kyc", "kind": "must_skill", "label": "KYC", "verdict": "met", "points": 3, "max_points": 3, "evidence": [{"quote": "KYC, AML, Excel", "verified": True, "match_score": 100}]}], scoring_input="<cv>KYC, AML, Excel</cv>", model="mock", prompt_version="test", latency_ms=0))
    db.flush()
    return requisition, candidate, application


def test_client_cannot_see_other_company_or_unsubmitted_applications(client):
    db = client.db_session
    requisition, candidate, application = _portal_application(db, "CND-PORTAL-OWN")
    _, _, unsubmitted = _portal_application(db, "CND-PORTAL-UNSUB", stage="sourced")
    kestrel_application = db.query(Application).join(Candidate).filter(Candidate.candidate_code == "CND-SMOKE").one()
    headers = _headers(client)

    assert client.get(f"/api/portal/applications/{kestrel_application.id}", headers=headers).status_code == 404
    assert client.get(f"/api/portal/applications/{unsubmitted.id}", headers=headers).status_code == 404
    listed = client.get(f"/api/portal/requisitions/{requisition.id}/candidates", headers=headers)
    assert listed.status_code == 200
    assert [row["candidate_code"] for row in listed.json()] == [candidate.candidate_code]
    assert client.get("/api/portal/requisitions", headers=headers).status_code == 200


def test_portal_masks_contact_fields_and_logs_profile_views(client):
    db = client.db_session
    requisition, candidate, application = _portal_application(db, "CND-PORTAL-MASK")
    headers = _headers(client)
    response = client.get(f"/api/portal/applications/{application.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Maya R."
    assert data["redacted_cv_text"] == candidate.redacted_text
    serialized = str(data).lower()
    assert "private@example.demo" not in serialized
    assert candidate.email.lower() not in serialized
    assert "9876543210" not in serialized
    assert "raw_text" not in data and "email" not in data and "phone" not in data
    assert db.query(AccessLog).filter_by(user_id=db.query(User).filter_by(email="priya@meridianbank.demo").one().id, candidate_id=candidate.id, action="view_portal_profile").count() == 1


def test_client_can_shortlist_and_propose_future_slots(client):
    db = client.db_session
    _, candidate, application = _portal_application(db, "CND-PORTAL-FEEDBACK")
    headers = _headers(client)
    shortlist = client.post(f"/api/portal/applications/{application.id}/feedback", headers=headers, json={"action": "shortlist", "note": "Good fit"})
    assert shortlist.status_code == 200
    assert shortlist.json()["status"] == "shortlisted"
    slots = [(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()]
    propose = client.post(f"/api/portal/applications/{application.id}/feedback", headers=headers, json={"action": "propose_interview", "proposed_slots": slots})
    assert propose.status_code == 200
    assert propose.json()["status"] == "shortlisted"
    feedback = db.query(ClientFeedback).filter_by(application_id=application.id, action="propose_interview").one()
    assert len(feedback.proposed_slots) == 2
    recruiter = db.query(User).filter_by(email="recruiter@companya.demo").one()
    assert "interview" in allowed_transitions(db, application, recruiter.role)
    assert db.query(StageEvent).filter_by(application_id=application.id, to_stage="shortlisted").count() == 1


def test_reject_requires_reason_and_note_for_other(client):
    db = client.db_session
    _, _, missing_reason = _portal_application(db, "CND-PORTAL-REASON")
    _, _, missing_note = _portal_application(db, "CND-PORTAL-NOTE")
    headers = _headers(client)
    no_reason = client.post(f"/api/portal/applications/{missing_reason.id}/feedback", headers=headers, json={"action": "reject"})
    no_note = client.post(f"/api/portal/applications/{missing_note.id}/feedback", headers=headers, json={"action": "reject", "reason_code": "other"})
    rejected = client.post(f"/api/portal/applications/{missing_reason.id}/feedback", headers=headers, json={"action": "reject", "reason_code": "notice_period", "note": "Notice is outside our timeline."})
    assert no_reason.status_code == 422
    assert no_note.status_code == 422
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "client_rejected"


def test_client_calling_recruiter_endpoints_gets_forbidden(client):
    headers = _headers(client)
    db = client.db_session
    requisition = db.query(Requisition).filter_by(title="Senior Java Developer").one()
    application = db.query(Application).join(Candidate).filter(Candidate.candidate_code == "CND-SMOKE").one()
    assert client.get(f"/api/requisitions/{requisition.id}/scorecard", headers=headers).status_code == 403
    assert client.get(f"/api/applications/{application.id}", headers=headers).status_code == 403
    assert client.post(f"/api/applications/{application.id}/stage", headers=headers, json={"stage": "withdrawn", "note": "test"}).status_code == 403
