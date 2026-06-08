"""E7/E8: /api/chat endpoint (PRD2 §9.1/§9.2) with injected pipeline + auth."""

import sys
from pathlib import Path

from app.auth import Principal, get_current_principal
from app.db import get_session
from app.main import app
from app.routers.chat import get_pipeline
from fastapi.testclient import TestClient


class _NoopSession:
    """Stand-in DB session for the audit write (ADR-0006) when there's no live DB."""

    def add(self, _obj) -> None:  # noqa: ANN001
        pass

    def commit(self) -> None:
        pass


# Reuse the shared RAG builder from the unit tests (repo root is parents[3]).
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "unit"))
from _ragkit import build_pipeline  # noqa: E402

client = TestClient(app)


def test_chat_401_without_token() -> None:
    # Auth runs before everything (ADR-0005): no bearer token → 401.
    resp = client.post("/api/chat", json={"message": "위약금"})
    assert resp.status_code == 401


def test_chat_returns_cited_answer() -> None:
    pipeline, _doc_a, _doc_b = build_pipeline("all")
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[get_current_principal] = lambda: Principal(sub="admin", role="admin")
    app.dependency_overrides[get_session] = lambda: _NoopSession()
    try:
        resp = client.post("/api/chat", json={"message": "위약금 얼마", "mode": "answer"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"]
        assert body["citations"]
        assert body["citations"][0]["page_no"] == 1
        assert "groundedness" in body["confidence"]
        assert body["retrieval_trace_id"]
    finally:
        app.dependency_overrides.clear()
