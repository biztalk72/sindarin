"""Reindex tool — re-embeds persisted chunks into a target collection (dev→live switch)."""

from __future__ import annotations

from uuid import uuid4

from app.reindex import reindex_corpus
from rag_core import DeterministicEmbedder, InMemoryVectorStore


class _Chunk:
    """Stand-in for db.DocumentChunk (avoids a live DB for the unit test)."""

    def __init__(self, chunk_id: str, text: str):
        self.chunk_id = chunk_id
        self.text = text
        self.document_id = uuid4()
        self.document_version_id = None
        self.section_id = None
        self.page_no = 1
        self.toc_path = ["계약"]
        self.bbox = None
        self.security_level = "internal"


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _Session:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _stmt):
        return _Scalars(self._rows)


def test_reindex_embeds_all_chunks_into_collection() -> None:
    rows = [_Chunk("c0", "계약 해지 위약금"), _Chunk("c1", "급여 지급일")]
    store = InMemoryVectorStore()
    embedder = DeterministicEmbedder(dim=48)

    n = reindex_corpus(
        _Session(rows),
        embedder=embedder,
        store=store,
        collection="documents_live",
        embedding_model="m-live",
        embedding_version="v2",
    )
    assert n == 2
    # Both chunks are searchable in the new collection with the new embedding model recorded.
    hits = store.search("documents_live", embedder.embed(["위약금"])[0], top_k=2)
    assert {h.chunk_id for h in hits} == {"c0", "c1"}
    assert all(h.payload["embedding_model"] == "m-live" for h in hits)


def test_reindex_empty_corpus_is_noop() -> None:
    assert reindex_corpus(
        _Session([]),
        embedder=DeterministicEmbedder(dim=8),
        store=InMemoryVectorStore(),
        collection="x",
        embedding_model="m",
        embedding_version="v1",
    ) == 0
