from app.db import SessionLocal
from app.models import AccessLog, Application, Candidate, CvBlob, CvFile, Requisition, UploadBatch


def _auth(client, email="recruiter@companya.demo"):
    response = client.post("/api/auth/login", json={"email": email, "password": "Demo@1234"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _duplicate(db, candidate_code, original, batch, requisition, status="needs_review"):
    duplicate = Candidate(candidate_code=candidate_code, full_name="Similar Candidate", duplicate_of_id=original.id, raw_text="CV text", redacted_text="CV text", skills=[], parse_confidence="medium", consent_status="pending")
    db.add(duplicate)
    db.flush()
    file = CvFile(batch_id=batch.id, candidate_id=duplicate.id, filename=f"{candidate_code}.pdf", mime="application/pdf", size_bytes=4, status=status)
    db.add(file)
    db.flush()
    db.add(CvBlob(cv_file_id=file.id, data=b"%PDF"))
    application = Application(requisition_id=requisition.id, candidate_id=duplicate.id, cv_file_id=file.id, stage="sourced")
    db.add(application)
    db.commit()
    return duplicate.id, application.id, file.id


def test_candidate_detail_logs_access_and_shows_possible_duplicate(client):
    headers = _auth(client)
    db = SessionLocal()
    original = db.query(Candidate).filter_by(candidate_code="CND-SMOKE").one()
    batch = db.query(UploadBatch).one()
    requisition = db.query(Requisition).one()
    candidate_id, application_id, _ = _duplicate(db, "CND-REVIEW-DUP", original, batch, requisition)
    response = client.get(f"/api/applications/{application_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["duplicate_of"]["candidate_code"] == "CND-SMOKE"
    assert client.db_session.query(AccessLog).filter_by(candidate_id=candidate_id, action="view_profile").count() == 1
    db.close()


def test_recruiter_can_mark_not_duplicate_and_merge(client):
    headers = _auth(client)
    db = SessionLocal()
    original = db.query(Candidate).filter_by(candidate_code="CND-SMOKE").one()
    batch = db.query(UploadBatch).one()
    requisition = db.query(Requisition).one()
    clear_id, _, clear_file_id = _duplicate(db, "CND-CLEAR-DUP", original, batch, requisition)
    merge_id, _, merged_file_id = _duplicate(db, "CND-MERGE-DUP", original, batch, requisition)
    db.close()

    response = client.post(f"/api/candidates/{clear_id}/not-duplicate", headers=headers, json={})
    assert response.status_code == 200
    db = client.db_session
    assert db.get(Candidate, clear_id).duplicate_of_id is None
    assert db.get(CvFile, clear_file_id).status == "done"

    response = client.post(f"/api/candidates/{merge_id}/merge", headers=headers, json={})
    assert response.status_code == 200
    original = db.query(Candidate).filter_by(candidate_code="CND-SMOKE").one()
    assert db.get(Candidate, merge_id) is None
    assert db.get(CvFile, merged_file_id).candidate_id == original.id


def test_client_cannot_read_recruiter_scorecard_or_mutate_candidates(client):
    headers = _auth(client, "priya@meridianbank.demo")
    with SessionLocal() as db:
        requisition = db.query(Requisition).one()
        candidate = db.query(Candidate).filter_by(candidate_code="CND-SMOKE").one()
    assert client.get(f"/api/requisitions/{requisition.id}/scorecard", headers=headers).status_code == 403
    assert client.post(f"/api/candidates/{candidate.id}/not-duplicate", headers=headers, json={}).status_code == 403
