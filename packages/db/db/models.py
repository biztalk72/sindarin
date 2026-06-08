"""Relational tables (PRD2 §6.2).

FK target ``users`` is added (PRD2 §6.2 names owner_id / principal_id / actor_id without a
table). Enum-like columns are strings carrying ``hybrid_idp_shared`` values.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, created_at, pk_uuid


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk_uuid()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # hybrid_idp_shared.Role
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)  # local login
    created_at: Mapped[dt.datetime] = created_at()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = pk_uuid()
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # document_ir.DocumentType
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    security_level: Mapped[str] = mapped_column(String(32), nullable=False)  # SecurityLevel
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # IngestionStage
    created_at: Mapped[dt.datetime] = created_at()

    versions: Mapped[list[DocumentVersion]] = relationship(back_populates="document")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_no"),)

    id: Mapped[uuid.UUID] = pk_uuid()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[dt.datetime] = created_at()

    document: Mapped[Document] = relationship(back_populates="versions")


class DocumentBlock(Base):
    """IR block mirror (PRD2 §6.1/§6.2). ``block_ref`` is the IR string block_id."""

    __tablename__ = "document_blocks"

    id: Mapped[uuid.UUID] = pk_uuid()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id"), nullable=True
    )
    block_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")  # document order
    section_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    section_path: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_type: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class DocumentChunk(Base):
    """Persisted retrieval chunk (E6/E7). Hydrates the RAG corpus + BM25; the matching vector
    lives in Qdrant keyed by ``chunk_id`` (vector payload omits text, PRD2 §6.3)."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = pk_uuid()
    chunk_id: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    toc_path: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    security_level: Mapped[str] = mapped_column(String(32), nullable=False)


class DocumentTable(Base):
    __tablename__ = "document_tables"

    id: Mapped[uuid.UUID] = pk_uuid()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    block_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_blocks.id"), nullable=True
    )
    schema_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    cells_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class DocumentKeyword(Base):
    __tablename__ = "document_keywords"

    id: Mapped[uuid.UUID] = pk_uuid()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    section_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class DocumentEntity(Base):
    __tablename__ = "document_entities"

    id: Mapped[uuid.UUID] = pk_uuid()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    entity: Mapped[str] = mapped_column(String(256), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_block_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_blocks.id"), nullable=True
    )


class KeywordEdge(Base):
    __tablename__ = "keyword_edges"

    id: Mapped[uuid.UUID] = pk_uuid()
    source_keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    target_keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    scope: Mapped[str | None] = mapped_column(String(128), nullable=True)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = pk_uuid()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # IngestionStage
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    logs: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = created_at()


class AclEntry(Base):
    """Document/collection permission (PRD2 §6.2). Enforced as ACL double-check (invariant #2)."""

    __tablename__ = "acl_entries"
    __table_args__ = (
        UniqueConstraint("resource_id", "resource_type", "principal_id", "permission"),
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)  # document | collection
    principal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False)  # read | write | manage


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = pk_uuid()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[dt.datetime] = created_at()


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = pk_uuid()
    dataset: Mapped[str] = mapped_column(String(128), nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[dt.datetime] = created_at()
