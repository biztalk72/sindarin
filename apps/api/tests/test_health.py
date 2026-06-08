"""Smoke test for the liveness endpoint (admin health moved to routers/admin.py, auth-only)."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_admin_health_requires_auth() -> None:
    # /api/admin/health is now admin-only (E11) — no token → 401.
    assert client.get("/api/admin/health").status_code == 401
