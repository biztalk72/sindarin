"""Shared builder for RAG pipeline tests (not a test module)."""

from __future__ import annotations

from uuid import UUID, uuid4

from rag_core import (
    BM25Index,
    ChunkRecord,
    DeterministicEmbedder,
    DeterministicGenerator,
    InMemoryVectorStore,
    RagPipeline,
)


class FakeAuthorizer:
    def __init__(self, allowed: set[UUID] | None) -> None:
        self._allowed = allowed

    def allowed_documents(self, principals: set[str]) -> set[UUID] | None:  # noqa: ARG002
        return self._allowed


def build_pipeline(allow: str = "all", *, dim: int = 64):
    """Returns (pipeline, doc_a_id, doc_b_id). doc A = 계약/위약금, doc B = 급여.

    ``allow`` selects what the principal may read (the authoritative ACL): "all" (admin),
    "none", "a", or "b" — mapped to the doc ids this builder creates.
    """
    doc_a, doc_b = uuid4(), uuid4()
    records = {
        "a0": ChunkRecord(
            chunk_id="a0",
            text="계약 해지 시 위약금은 100만원이다.",
            document_id=doc_a,
            page_no=1,
            toc_path=["계약", "해지"],
            security_level="internal",
        ),
        "b0": ChunkRecord(
            chunk_id="b0",
            text="급여는 매월 25일에 지급한다.",
            document_id=doc_b,
            page_no=1,
            toc_path=["급여"],
            security_level="confidential",
        ),
    }
    embedder = DeterministicEmbedder(dim=dim)
    store = InMemoryVectorStore()
    store.ensure_collection("documents", dim)
    store.upsert(
        "documents",
        [
            (cid, embedder.embed([r.text])[0],
             {"document_id": str(r.document_id), "security_level": r.security_level})
            for cid, r in records.items()
        ],
    )
    bm25 = BM25Index()
    bm25.index([(cid, r.text) for cid, r in records.items()])

    allowed: set[UUID] | None = {
        "all": None,
        "none": set(),
        "a": {doc_a},
        "b": {doc_b},
    }[allow]

    pipeline = RagPipeline(
        embedder=embedder,
        store=store,
        bm25=bm25,
        corpus=records,
        authorizer=FakeAuthorizer(allowed),
        generator=DeterministicGenerator(),
        collection="documents",
    )
    return pipeline, doc_a, doc_b
