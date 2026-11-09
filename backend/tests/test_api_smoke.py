from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import Application, Candidate, Client, CvFile, Requisition, Scorecard, UploadBatch, User


def _token(client, email: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Demo@1234"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _portal_smoke_application(db):
    meridian = db.query(Client).filter_by(name="Meridian Bank").one()
    recruiter = db.query(User).filter_by(email="recruiter@companya.demo").one()
    requisition = Requisition(
        client_id=meridian.id,
        owner_id=recruiter.id,
        title="Portal smoke role",
        location="Noida",
        jd_text="Portal smoke test role",
        openings=1,
        status="open",
    )
    db.add(requisition)
    db.flush()
    db.add(Scorecard(requisition_id=requisition.id, version=1, is_active=True, created_by=recruiter.id, criteria=[]))
    candidate = Candidate(
        candidate_code="CND-PORTAL-SMOKE",
        full_name="Portal Smoke Candidate",
        current_role="Analyst",
        skills=[],
        raw_text="Analyst",
        redacted_text="Analyst",
        consent_status="granted",
    )
    db.add(candidate)
    db.flush()
    batch = UploadBatch(requisition_id=requisition.id, uploaded_by=recruiter.id, total=1, processed=1, failed=0, duplicates=0, status="done")
    db.add(batch)
    db.flush()
    cv_file = CvFile(batch_id=batch.id, candidate_id=candidate.id, filename="portal-smoke.pdf", mime="application/pdf", size_bytes=4, status="done")
    db.add(cv_file)
    db.flush()
    submitted_at = datetime.now(timezone.utc)
    application = Application(
        requisition_id=requisition.id,
        candidate_id=candidate.id,
        cv_file_id=cv_file.id,
        stage="submitted",
        recruiter_opened_at=submitted_at,
        submitted_at=submitted_at,
        submitted_by=recruiter.id,
    )
    db.add(application)
    db.flush()
    return requisition, application


def test_every_get_endpoint_works_for_an_authorized_role(client):
    recruiter_headers = {"Authorization": f"Bearer {_token(client, 'recruiter@companya.demo')}"}
    head_headers = {"Authorization": f"Bearer {_token(client, 'head@companya.demo')}"}
    client_headers = {"Authorization": f"Bearer {_token(client, 'priya@meridianbank.demo')}"}

    requisition, portal_application = _portal_smoke_application(client.db_session)
    with SessionLocal() as db:
        requisition_id = db.query(Requisition).filter_by(title="Senior Java Developer").one().id
        batch_id = db.query(UploadBatch).one().id
        cv_id = db.query(CvFile).filter_by(filename="smoke.pdf").one().id
        application_id = db.query(Application).filter_by(candidate_id=db.query(CvFile).filter_by(id=cv_id).one().candidate_id).one().id
        candidate_id = db.query(CvFile).filter_by(id=cv_id).one().candidate_id

    checks = [
        ("/health", None),
        ("/api/health", None),
        ("/api/meta", None),
        ("/api/auth/me", recruiter_headers),
        ("/api/auth/me", client_headers),
        ("/api/auth/recruiter-check", recruiter_headers),
        ("/api/requisitions", recruiter_headers),
        ("/api/requisitions", client_headers),
        ("/api/requisitions/clients", recruiter_headers),
        ("/api/requisitions/clients", client_headers),
        (f"/api/requisitions/{requisition_id}", recruiter_headers),
        (f"/api/requisitions/{requisition_id}/scorecard", recruiter_headers),
        (f"/api/requisitions/{requisition_id}/summary", recruiter_headers),
        (f"/api/requisitions/{requisition_id}/applications", recruiter_headers),
        (f"/api/requisitions/{requisition_id}/pipeline", recruiter_headers),
        (f"/api/requisitions/{requisition.id}", client_headers),
        ("/api/portal/requisitions", client_headers),
        (f"/api/portal/requisitions/{requisition.id}/candidates", client_headers),
        (f"/api/portal/applications/{portal_application.id}", client_headers),
        ("/api/uploads/latest", recruiter_headers),
        (f"/api/uploads/latest?requisition_id={requisition_id}", recruiter_headers),
        (f"/api/uploads/{batch_id}", recruiter_headers),
        (f"/api/cv-files/{cv_id}/redacted", recruiter_headers),
        (f"/api/applications/{application_id}", recruiter_headers),
        (f"/api/applications/{application_id}/cv", recruiter_headers),
        ("/api/insights/calibration", head_headers),
        (f"/api/candidates/{candidate_id}/access-log", head_headers),
    ]

    for path, headers in checks:
        response = client.get(path, headers=headers or {})
        assert response.status_code == 200, f"GET {path}: {response.status_code} {response.text}"

    client_rows = client.get("/api/requisitions/clients", headers=client_headers).json()
    assert [row["name"] for row in client_rows] == ["Meridian Bank"]
