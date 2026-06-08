"""Post-deploy smoke tests (PRD2 §13 deploy → smoke). Runs against a live deployment via
SMOKE_BASE_URL (default the local dev api). Marked `e2e`; skips if the target is unreachable.

Exercises the critical path end-to-end through HTTP: health → login → authenticated
documents list → chat (200 with ingested docs, or 503 on a fresh empty deploy).
"""

import os

import httpx
import pytest

pytestmark = pytest.mark.e2e

BASE = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
ADMIN_EMAIL = os.environ.get("IDP_BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
ADMIN_PW = os.environ.get("IDP_BOOTSTRAP_ADMIN_PASSWORD", "changeme-admin-pw")


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    try:
        httpx.get(f"{BASE}/api/health", timeout=3.0)
    except Exception:  # noqa: BLE001
        pytest.skip(f"deployment not reachable at {BASE}")
    with httpx.Client(base_url=BASE, timeout=15.0) as c:
        yield c


def test_health(client: httpx.Client) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_requires_auth(client: httpx.Client) -> None:
    assert client.post("/api/chat", json={"message": "x"}).status_code == 401


def test_login_and_authenticated_path(client: httpx.Client) -> None:
    login = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/auth/me", headers=headers).json()["role"] == "admin"
    assert client.get("/api/documents", headers=headers).status_code == 200

    # 200 once documents are ingested; 503 on a fresh empty deploy — both are healthy states.
    chat = client.post("/api/chat", json={"message": "smoke"}, headers=headers)
    assert chat.status_code in (200, 503)
