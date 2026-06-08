"""ADR-0005: documents + upload endpoints require a valid token (no token → 401)."""

from uuid import uuid4

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_documents_list_requires_auth() -> None:
    assert client.get("/api/documents").status_code == 401


def test_document_insight_requires_auth() -> None:
    did = uuid4()
    assert client.get(f"/api/documents/{did}/toc").status_code == 401
    assert client.get(f"/api/documents/{did}/keywords").status_code == 401
    assert client.get(f"/api/documents/{did}/graph").status_code == 401
    assert client.get(f"/api/documents/{did}/preview").status_code == 401


def test_jobs_requires_auth() -> None:
    assert client.get(f"/api/ingest/jobs/{uuid4()}").status_code == 401


def test_upload_requires_auth() -> None:
    resp = client.post("/api/upload", files={"file": ("x.csv", "a,b\n1,2\n", "text/csv")})
    assert resp.status_code == 401


def test_admin_requires_auth() -> None:
    for path in ("/api/admin/health", "/api/admin/metrics", "/api/admin/jobs", "/api/admin/audit"):
        assert client.get(path).status_code == 401


def test_admin_forbidden_for_non_admin() -> None:
    from app.auth import Principal, get_current_principal

    app.dependency_overrides[get_current_principal] = lambda: Principal(sub="u-1", role="user")
    try:
        assert client.get("/api/admin/health").status_code == 403
        assert client.get("/api/admin/metrics").status_code == 403
    finally:
        app.dependency_overrides.clear()
