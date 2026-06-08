"""Corpus + ACL repository (E7 data layer).

Loads the RAG corpus (chunk text + metadata) from ``document_chunks`` and builds the BM25
index from it; the authoritative ACL check reads ``acl_entries`` (the Postgres side of the
double-check, invariant #2). ``admin`` in the principal set means unrestricted (ADR-0005).
"""

from __future__ import annotations

from uuid import UUID

from db import AclEntry, DocumentChunk
from rag_core import BM25Index, ChunkRecord
from sqlalchemy import select
from sqlalchemy.orm import Session

ADMIN_PRINCIPAL = "admin"


def load_corpus(session: Session) -> dict[str, ChunkRecord]:
    rows = session.execute(select(DocumentChunk)).scalars().all()
    return {
        row.chunk_id: ChunkRecord(
            chunk_id=row.chunk_id,
            text=row.text,
            document_id=row.document_id,
            page_no=row.page_no,
            section_id=row.section_id,
            toc_path=list(row.toc_path or []),
            bbox=row.bbox,
            security_level=row.security_level,
        )
        for row in rows
    }


def build_bm25(corpus: dict[str, ChunkRecord]) -> BM25Index:
    bm25 = BM25Index()
    bm25.index([(cid, rec.text) for cid, rec in corpus.items()])
    return bm25


class PostgresAuthorizer:
    """Authoritative per-document ACL from ``acl_entries`` (invariant #2)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def allowed_documents(self, principals: set[str]) -> set[UUID] | None:
        if ADMIN_PRINCIPAL in principals:
            return None  # unrestricted
        principal_uuids: set[UUID] = set()
        for p in principals:
            try:
                principal_uuids.add(UUID(p))
            except (ValueError, AttributeError):
                continue
        if not principal_uuids:
            return set()
        rows = self._session.execute(
            select(AclEntry.resource_id).where(
                AclEntry.resource_type == "document",
                AclEntry.principal_id.in_(principal_uuids),
                AclEntry.permission.in_(["read", "write", "manage"]),
            )
        ).all()
        return {r[0] for r in rows}
