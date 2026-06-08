"""Hybrid retrieval + ACL double-check (E7, ADR-0008, PRD2 §7).

Vector candidates (semantic) and BM25 candidates (exact term / 법령명) are fused with
Reciprocal Rank Fusion, then the ACL double-check runs: the vector ``payload_filter`` is the
first cut (security scope), and an authoritative per-document ``Authorizer`` (Postgres
``acl_entries`` in prod) is the second — invariant #2. Chunk text/metadata is hydrated from a
``corpus`` lookup (the vector payload deliberately omits raw text, PRD2 §6.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from rag_core.embedder import Embedder
from rag_core.keyword_index import BM25Index
from rag_core.vectorstore import VectorStore

RRF_K = 60


@dataclass
class ChunkRecord:
    chunk_id: str
    text: str
    document_id: UUID
    page_no: int | None = None
    section_id: str | None = None
    toc_path: list[str] = field(default_factory=list)
    bbox: dict[str, Any] | None = None
    security_level: str | None = None


@dataclass
class Candidate:
    record: ChunkRecord
    score: float
    sources: list[str]  # "vector" and/or "keyword"


class Authorizer(Protocol):
    """Authoritative per-document ACL check (Postgres ``acl_entries`` in prod)."""

    def allowed_documents(self, principals: set[str]) -> set[UUID] | None:
        """Return the document_ids the principals may read, or None for 'all' (admin)."""
        ...


def _rrf(rankings: list[list[str]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


def hybrid_retrieve(
    query: str,
    *,
    embedder: Embedder,
    store: VectorStore,
    collection: str,
    bm25: BM25Index,
    corpus: dict[str, ChunkRecord],
    top_k: int = 10,
    payload_filter: dict[str, list[Any]] | None = None,
) -> list[Candidate]:
    qvec = embedder.embed([query])[0]
    vec_ids = [
        h.chunk_id
        for h in store.search(collection, qvec, top_k=top_k, payload_filter=payload_filter)
    ]
    kw_ids = [cid for cid, _ in bm25.search(query, top_k=top_k)]

    fused = _rrf([vec_ids, kw_ids])
    sources_by_id: dict[str, list[str]] = {}
    for cid in vec_ids:
        sources_by_id.setdefault(cid, []).append("vector")
    for cid in kw_ids:
        sources_by_id.setdefault(cid, []).append("keyword")

    candidates = [
        Candidate(record=corpus[cid], score=score, sources=sources_by_id.get(cid, []))
        for cid, score in fused.items()
        if cid in corpus
    ]
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:top_k]


def acl_filter(
    candidates: list[Candidate],
    principals: set[str],
    authorizer: Authorizer,
) -> list[Candidate]:
    """Drop candidates whose document the principals may not read (Postgres double-check)."""
    allowed = authorizer.allowed_documents(principals)
    if allowed is None:  # admin / unrestricted
        return candidates
    return [c for c in candidates if c.record.document_id in allowed]
