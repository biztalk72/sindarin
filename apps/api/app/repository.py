"""Corpus + ACL repository (E7 data layer).

Loads the RAG corpus (chunk text + metadata) from ``document_chunks`` and builds the BM25
index from it; the authoritative ACL check reads ``acl_entries`` (the Postgres side of the
double-check, invariant #2). ``admin`` in the principal set means unrestricted (ADR-0005).

Principals are typed (``user`` UUID strings + role names). The authorizer treats role names
and user UUIDs as a single set of candidate ``principal_id`` values, scoped by
``principal_type`` so a UUID-shaped role name (unlikely but possible) can't cross-match.
"""

from __future__ import annotations

from uuid import UUID

from db import AclEntry, DocumentChunk
from rag_core import BM25Index, ChunkRecord
from sqlalchemy import or_, select, tuple_
from sqlalchemy.orm import Session

ADMIN_PRINCIPAL = "admin"
_KNOWN_ROLES = {"user", "document_manager", "auditor"}  # admin shortcuts before this


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


def _split_principals(principals: set[str]) -> tuple[set[str], set[str]]:
    """Partition the caller's principals into (user_uuids, role_names).

    A principal that parses as a UUID is treated as the caller's ``sub``; otherwise it's a
    role name. Anything that's neither a known role nor a UUID is dropped so a stray claim
    can't widen the visible document set.
    """
    user_ids: set[str] = set()
    roles: set[str] = set()
    for p in principals:
        try:
            user_ids.add(str(UUID(p)))
            continue
        except (ValueError, AttributeError):
            pass
        if p in _KNOWN_ROLES:
            roles.add(p)
    return user_ids, roles


class PostgresAuthorizer:
    """Authoritative per-document ACL from ``acl_entries`` (invariant #2)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def allowed_documents(self, principals: set[str]) -> set[UUID] | None:
        if ADMIN_PRINCIPAL in principals:
            return None  # unrestricted
        user_ids, roles = _split_principals(principals)
        if not user_ids and not roles:
            return set()
        clauses = []
        if user_ids:
            clauses.append(
                tuple_(AclEntry.principal_type, AclEntry.principal_id).in_(
                    [("user", uid) for uid in user_ids]
                )
            )
        if roles:
            clauses.append(
                tuple_(AclEntry.principal_type, AclEntry.principal_id).in_(
                    [("role", r) for r in roles]
                )
            )
        rows = self._session.execute(
            select(AclEntry.resource_id).where(
                AclEntry.resource_type == "document",
                AclEntry.permission.in_(["read", "write", "manage"]),
                or_(*clauses),
            )
        ).all()
        return {r[0] for r in rows}
