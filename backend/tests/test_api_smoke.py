from app.db import SessionLocal
from app.models import Application, CvFile, Requisition, UploadBatch


def _token(client, email: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Demo@1234"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_every_get_endpoint_works_for_an_authorized_role(client):
    recruiter_headers = {"Authorization": f"Bearer {_token(client, 'recruiter@companya.demo')}"}
    client_headers = {"Authorization": f"Bearer {_token(client, 'priya@meridianbank.demo')}"}

    with SessionLocal() as db:
        requisition_id = db.query(Requisition).filter_by(title="Senior Java Developer").one().id
        batch_id = db.query(UploadBatch).one().id
        cv_id = db.query(CvFile).filter_by(filename="smoke.pdf").one().id
        application_id = db.query(Application).filter_by(candidate_id=db.query(CvFile).filter_by(id=cv_id).one().candidate_id).one().id

    checks = [
        ("/health", None),
        ("/api/health", None),
        ("/api/meta", None),
        ("/api/auth/me", recruiter_headers),
        ("/api/auth/me", client_headers),
        ("/api/auth/recruiter-check", recruiter_headers),
        ("/api/requisitions", recruiter_headers),
        ("/api/requisitions", client_headers),
        (f"/api/requisitions/{requisition_id}", recruiter_headers),
        (f"/api/requisitions/{requisition_id}/scorecard", recruiter_headers),
        (f"/api/requisitions/{requisition_id}/summary", recruiter_headers),
        (f"/api/requisitions/{requisition_id}/applications", recruiter_headers),
        (f"/api/requisitions/{requisition_id}/pipeline", recruiter_headers),
        ("/api/uploads/latest", recruiter_headers),
        (f"/api/uploads/latest?requisition_id={requisition_id}", recruiter_headers),
        (f"/api/uploads/{batch_id}", recruiter_headers),
        (f"/api/cv-files/{cv_id}/redacted", recruiter_headers),
        (f"/api/applications/{application_id}", recruiter_headers),
        (f"/api/applications/{application_id}/cv", recruiter_headers),
    ]

    for path, headers in checks:
        response = client.get(path, headers=headers or {})
        assert response.status_code == 200, f"GET {path}: {response.status_code} {response.text}"
