import pytest
from fastapi.testclient import TestClient

from app.core.config import DEFAULT_CORS_ORIGINS, get_cors_origins
from app.main import app

client = TestClient(app)


def test_root_returns_project_status() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "CarbonGuard API is running.",
        "status": "service_ready",
    }


def test_health_returns_application_details() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "application": "CarbonGuard API",
        "version": "0.1.0",
    }


def test_status_reports_current_phase() -> None:
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["phase"] == "Phase 8"
    assert response.json()["status"] == "release_validation_complete"
    assert response.json()["next_phase"] == "none"


def test_security_headers_are_present_on_api_responses() -> None:
    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_cors_allows_configured_local_frontend_and_rejects_unknown_origin() -> None:
    preflight = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert (
        preflight.headers["access-control-allow-origin"]
        == "http://127.0.0.1:5173"
    )
    assert "access-control-allow-credentials" not in preflight.headers

    denied = client.get("/api/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in denied.headers


def test_cors_configuration_requires_explicit_valid_production_origins(monkeypatch):
    monkeypatch.setenv("CARBONGUARD_ENVIRONMENT", "development")
    monkeypatch.delenv("CARBONGUARD_CORS_ORIGINS", raising=False)
    assert get_cors_origins() == list(DEFAULT_CORS_ORIGINS)

    monkeypatch.setenv("CARBONGUARD_ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="must be configured in production"):
        get_cors_origins()

    monkeypatch.setenv("CARBONGUARD_CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="HTTP\\(S\\) origins"):
        get_cors_origins()

    monkeypatch.setenv("CARBONGUARD_CORS_ORIGINS", "https://dashboard.example/path")
    with pytest.raises(RuntimeError, match="HTTP\\(S\\) origins"):
        get_cors_origins()

    monkeypatch.setenv("CARBONGUARD_CORS_ORIGINS", "https://dashboard.example:bad")
    with pytest.raises(RuntimeError, match="invalid port"):
        get_cors_origins()

    monkeypatch.setenv(
        "CARBONGUARD_CORS_ORIGINS",
        "https://dashboard.example, https://dashboard.example/",
    )
    assert get_cors_origins() == ["https://dashboard.example"]


def test_oversized_request_body_is_rejected_before_route_validation() -> None:
    response = client.post(
        "/api/experiments",
        content=b"x" * (1_048_576 + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body must not exceed 1048576 bytes"
    assert response.headers["x-content-type-options"] == "nosniff"
