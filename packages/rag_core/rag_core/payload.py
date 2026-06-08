"""Vector DB payload contract (PRD2 §6.3 / ADR-0008).

Every chunk stored in the vector DB carries this payload so ACL double-check, citation,
keyword/entity filtering, UI interaction, and blue/green reindex all work off the store.
The citation anchor (``document_id``, ``page_no``, ``bbox``) is carried verbatim from the
Document IR so invariant #3 / ADR-0004 holds through retrieval.
"""

from __future__ import annotations

from uuid import UUID

from document_ir import BBox
from hybrid_idp_shared import SecurityLevel
from pydantic import BaseModel, Field


class ChunkPayload(BaseModel):
    chunk_id: str
    document_id: UUID
    document_version_id: UUID
    section_id: str | None = None
    toc_path: list[str] = Field(default_factory=list)
    page_no: int | None = None
    bbox: BBox | None = None
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    security_level: SecurityLevel
    acl_hash: str
    ocr_confidence: float | None = None
    parser: str
    embedding_model: str
    embedding_version: str
