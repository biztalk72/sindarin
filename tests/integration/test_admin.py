"""E11 (live): admin observability endpoints return real component health + metrics."""

import pytest
from app.auth import Principal, get_current_principal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration

DB_URL = "postgresql+psycopg://hybrid_idp:replace-me@localhost:5433/hybrid_idp"
QDRANT_URL = "http://localhost:6333"


@pytest.fixture
def admin_client(monkeypatch):
    try:
        engine = create_engine(DB_URL)
        engine.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("Postgres not reachable on " + DB_URL)

    from app.config import settings
    from app.db import get_session
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(settings, "vector_db_url", QDRANT_URL)  # host-reachable Qdrant
    s = sessionmaker(bind=engine)()
    app.dependency_overrides[get_session] = lambda: s
    app.dependency_overrides[get_current_principal] = lambda: Principal(sub="admin", role="admin")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        s.close()


def test_admin_health_checks_components(admin_client) -> None:
    body = admin_client.get("/api/admin/health").json()
    assert body["components"]["postgres"] == "ok"
    assert body["components"]["vector_db"] == "ok"
    assert body["status"] == "ok"


def test_admin_metrics_shape(admin_client) -> None:
    m = admin_client.get("/api/admin/metrics").json()
    assert isinstance(m["documents"], int) and m["documents"] >= 0
    assert isinstance(m["chunks"], int)
    assert isinstance(m["ingestion_jobs"], dict)
    assert "gb10_telemetry" in m


def test_admin_jobs_and_audit_lists(admin_client) -> None:
    jobs = admin_client.get("/api/admin/jobs").json()
    assert isinstance(jobs, list)
    assert all("stage" in j and "status" in j and "metrics" in j for j in jobs)

    audit = admin_client.get("/api/admin/audit").json()
    assert isinstance(audit, list)
