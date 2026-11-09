from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings, settings
from app.db import engine, normalize_database_url
from app.routers import auth
from sqlalchemy.exc import SQLAlchemyError


def test_production_requires_a_non_default_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET must be set"):
        Settings(_env_file=None, env="production")
    configured = Settings(_env_file=None, env="production", jwt_secret="a-long-production-secret")
    assert configured.env == "production"


def test_neon_url_uses_psycopg_and_requires_tls():
    url = normalize_database_url("postgresql://user:password@ep-example.neon.tech/shortlist")
    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "require"


def test_login_rate_limit_applies_only_in_production(monkeypatch):
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(auth, "_login_rate_limit", 2)
    request = SimpleNamespace(client=SimpleNamespace(host=f"rate-test-{uuid4()}"))

    auth._enforce_login_rate_limit(request)
    auth._enforce_login_rate_limit(request)
    with pytest.raises(HTTPException) as error:
        auth._enforce_login_rate_limit(request)
    assert error.value.status_code == 429
    assert error.value.detail["code"] == "login_rate_limited"


def test_security_headers_and_database_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_production_adds_hsts_header(client, monkeypatch):
    monkeypatch.setattr(settings, "env", "production")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_database_health_reports_unavailable_when_select_fails(client, monkeypatch):
    def fail_connect():
        raise SQLAlchemyError("unavailable")

    monkeypatch.setattr(engine, "connect", fail_connect)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
