"""E7 end-to-end (live): ingest documents, then /api/chat returns grounded cited answers.

Runs against the dev stack (Postgres :5433, Qdrant :6333). Uses dev-mode components
(deterministic embedder + extractive generator) so it needs no external LLM — the answer is
a real, grounded, citation-validated extract from the ingested document. Skips if the stack
isn't reachable; cleans up its DB rows and Qdrant collection.
"""

import uuid

import pytest
from app.config import Settings
from app.ingest import ingest_ir
from app.rag import build_pipeline_from_db, embedding_descriptor, select_embedder
from document_ir import Block, BlockType, DocumentIR, DocumentType, Quality
from rag_core import QdrantVectorStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration

DB_URL = "postgresql+psycopg://hybrid_idp:replace-me@localhost:5433/hybrid_idp"
QDRANT_URL = "http://localhost:6333"
TEST_COLLECTION = "test_e7_live"


def _settings() -> Settings:
    return Settings(
        openai_api_key="",  # dev mode (deterministic embed + extractive generate)
        embedding_model="",
        vector_db_url=QDRANT_URL,
        vector_collection=TEST_COLLECTION,
    )


def _ir(doc_id: uuid.UUID) -> DocumentIR:
    return DocumentIR(
        document_id=doc_id,
        source_uri="s3://test/contract.docx",
        document_type=DocumentType.DOCX,
        blocks=[
            Block(block_id="h1", block_type=BlockType.HEADING, text="위약금 조항", page_no=1, section_path=["계약"]),
            Block(
                block_id="p1",
                block_type=BlockType.PARAGRAPH,
                text="계약 해지 시 위약금은 100만원으로 한다.",
                page_no=1,
                section_path=["계약", "위약금"],
            ),
        ],
        quality=Quality(parser="markitdown"),
    )


@pytest.fixture
def session():
    try:
        engine = create_engine(DB_URL)
        engine.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("Postgres not reachable on " + DB_URL)
    store = QdrantVectorStore(QDRANT_URL)
    try:
        store._c().get_collections()
    except Exception:  # noqa: BLE001
        pytest.skip("Qdrant not reachable on " + QDRANT_URL)

    s = sessionmaker(bind=engine)()
    created_docs: list[uuid.UUID] = []
    yield s, store, created_docs

    # cleanup
    from db import (
        AclEntry,
        Document,
        DocumentBlock,
        DocumentChunk,
        DocumentVersion,
        IngestionJob,
    )

    for did in created_docs:
        s.query(DocumentChunk).filter_by(document_id=did).delete()
        s.query(DocumentBlock).filter_by(document_id=did).delete()
        s.query(IngestionJob).filter_by(document_id=did).delete()
        s.query(AclEntry).filter_by(resource_id=did).delete()
        s.query(DocumentVersion).filter_by(document_id=did).delete()
        s.query(Document).filter_by(id=did).delete()
    s.commit()
    s.close()
    try:
        store._c().delete_collection(TEST_COLLECTION)
    except Exception:  # noqa: BLE001
        pass


def test_ingest_then_pipeline_answers_with_citation(session) -> None:
    s, store, created = session
    settings = _settings()
    doc_id = uuid.uuid4()
    created.append(doc_id)
    model, version = embedding_descriptor(settings)

    _doc, n_chunks = ingest_ir(
        _ir(doc_id),
        name="contract.docx",
        session=s,
        embedder=select_embedder(settings),
        store=store,
        collection=TEST_COLLECTION,
        embedding_model=model,
        embedding_version=version,
    )
    assert n_chunks >= 1

    pipeline = build_pipeline_from_db(s, settings)
    res = pipeline.answer("위약금 얼마", principals={"admin"})
    assert "위약금" in res.answer
    assert res.citations
    assert res.citations[0].document_id == doc_id
    assert res.confidence["groundedness"] > 0


def test_upload_then_chat_over_http(session, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    s, store, created = session
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "vector_db_url", QDRANT_URL)
    monkeypatch.setattr(app_settings, "vector_collection", TEST_COLLECTION)

    from app.auth import Principal, get_current_principal
    from app.db import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: s
    # admin principal with a non-UUID sub → audit actor_id stays NULL (no FK to a seeded user).
    app.dependency_overrides[get_current_principal] = lambda: Principal(sub="admin", role="admin")
    client = TestClient(app)
    try:
        csv = "항목,금액\n위약금,1000000\n지연배상,500000\n"
        up = client.post("/api/upload", files={"file": ("fees.csv", csv, "text/csv")})
        assert up.status_code == 200, up.text
        doc_id = up.json()["document_id"]
        created.append(uuid.UUID(doc_id))
        assert up.json()["chunks"] >= 1

        chat = client.post("/api/chat", json={"message": "위약금 금액", "mode": "answer"})
        assert chat.status_code == 200, chat.text
        body = chat.json()
        assert body["citations"]
        assert body["retrieval_trace_id"]

        # Document library list reflects the upload (UI-DOC).
        docs = client.get("/api/documents")
        assert docs.status_code == 200
        listed = docs.json()
        assert any(d["name"] == "fees.csv" and d["chunk_count"] >= 1 for d in listed)
        assert all("status" in d and "type" in d for d in listed)

        # Insight endpoints (E10).
        toc = client.get(f"/api/documents/{doc_id}/toc")
        assert toc.status_code == 200 and "toc_tree" in toc.json()

        kws = client.get(f"/api/documents/{doc_id}/keywords")
        assert kws.status_code == 200
        words = {k["keyword"] for k in kws.json()["keywords"]}
        assert "위약금" in words

        graph = client.get(f"/api/documents/{doc_id}/graph")
        assert graph.status_code == 200
        assert len(graph.json()["nodes"]) >= 1

        preview = client.get(f"/api/documents/{doc_id}/preview")
        assert preview.status_code == 200
        pj = preview.json()
        assert pj["name"] == "fees.csv"
        assert len(pj["blocks"]) >= 1
        assert all("block_ref" in b and "text" in b for b in pj["blocks"])

        quality = client.get(f"/api/documents/{doc_id}/quality")
        assert quality.status_code == 200
        q = quality.json()
        assert q["status"] == "success"
        assert q["metrics"]["parser"] == "markitdown"
        assert q["metrics"]["chunks"] >= 1
    finally:
        app.dependency_overrides.clear()
