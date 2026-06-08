"""ADR-0005 (live): seed a user → /api/auth/login → bearer → /api/auth/me."""

import uuid

import pytest
from app.auth import hash_password
from db import User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration

DB_URL = "postgresql+psycopg://hybrid_idp:replace-me@localhost:5433/hybrid_idp"


@pytest.fixture
def session():
    try:
        engine = create_engine(DB_URL)
        engine.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("Postgres not reachable on " + DB_URL)
    s = sessionmaker(bind=engine)()
    created: list[uuid.UUID] = []
    yield s, created
    for uid in created:
        s.query(User).filter_by(id=uid).delete()
    s.commit()
    s.close()


def test_login_then_me(session) -> None:
    from app.db import get_session
    from app.main import app
    from fastapi.testclient import TestClient

    s, created = session
    email = "auth-flow-test@example.com"
    user = User(email=email, role="admin", password_hash=hash_password("pw-123456"))
    s.add(user)
    s.commit()
    created.append(user.id)

    app.dependency_overrides[get_session] = lambda: s
    client = TestClient(app)
    try:
        assert client.post("/api/auth/login", json={"email": email, "password": "nope"}).status_code == 401

        ok = client.post("/api/auth/login", json={"email": email, "password": "pw-123456"})
        assert ok.status_code == 200, ok.text
        token = ok.json()["access_token"]
        assert ok.json()["role"] == "admin"
        assert ok.json()["sub"] == str(user.id)

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json() == {"sub": str(user.id), "role": "admin"}

        assert client.get("/api/auth/me").status_code == 401  # no token
    finally:
        app.dependency_overrides.clear()
