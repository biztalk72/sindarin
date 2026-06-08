"""Synchronous ingestion (E6/E9): persist IR + index to the vector store.

Persists the document, version, blocks, retrieval chunks, an owner ACL entry, and the
ingestion job to Postgres, then embeds the chunks and upserts them (with the full
``ChunkPayload`` contract) into the vector store. Returns ``(document_id, n_chunks)``.

Embedder/store are injected so the SAME embedder used here is used at query time (vectors
must be comparable). The deterministic dev embedder makes this reproducible offline.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from db import (
    AclEntry,
    Document,
    DocumentBlock,
    DocumentChunk,
    DocumentKeyword,
    DocumentVersion,
    IngestionJob,
)
from document_ir import DocumentIR
from hybrid_idp_shared import SecurityLevel
from rag_core import ChunkPayload, Embedder, VectorStore, chunk_document
from sqlalchemy.orm import Session


def _acl_hash(principals: set[str]) -> str:
    return hashlib.sha256(",".join(sorted(principals)).encode("utf-8")).hexdigest()[:32]


def ingest_ir(
    ir: DocumentIR,
    *,
    name: str,
    session: Session,
    embedder: Embedder,
    store: VectorStore,
    collection: str,
    embedding_model: str,
    embedding_version: str,
    security_level: SecurityLevel = SecurityLevel.INTERNAL,
    owner_id: UUID | None = None,
) -> tuple[UUID, int]:
    session.add(
        Document(
            id=ir.document_id,
            name=name,
            type=ir.document_type.value,
            owner_id=owner_id,
            security_level=security_level.value,
            status="indexed",
        )
    )
    version = DocumentVersion(document_id=ir.document_id, version_no=1, source_uri=ir.source_uri)
    session.add(version)
    session.flush()

    for i, b in enumerate(ir.blocks):
        session.add(
            DocumentBlock(
                document_id=ir.document_id,
                document_version_id=version.id,
                block_ref=b.block_id,
                seq=i,
                section_id=b.section_id,
                section_path=list(b.section_path),
                page_no=b.page_no,
                block_type=b.block_type.value,
                text=b.text,
                bbox=b.bbox.model_dump() if b.bbox else None,
            )
        )

    chunks = chunk_document(ir)
    for c in chunks:
        session.add(
            DocumentChunk(
                chunk_id=c.chunk_id,
                document_id=ir.document_id,
                document_version_id=version.id,
                text=c.text,
                page_no=c.page_no,
                section_id=c.section_id,
                toc_path=c.toc_path,
                bbox=c.bbox.model_dump() if c.bbox else None,
                security_level=security_level.value,
            )
        )

    for kw in ir.semantic_keywords:
        session.add(
            DocumentKeyword(
                document_id=ir.document_id,
                keyword=kw.keyword,
                weight=kw.weight,
                confidence=kw.confidence,
            )
        )

    if owner_id is not None:
        session.add(
            AclEntry(
                resource_id=ir.document_id,
                resource_type="document",
                principal_id=owner_id,
                permission="read",
            )
        )
    session.add(
        IngestionJob(
            document_id=ir.document_id,
            stage="indexed",
            status="success",
            metrics={
                "parser": ir.quality.parser,
                "parser_version": ir.quality.parser_version,
                "extraction_coverage": ir.quality.extraction_coverage,
                "ocr_confidence": ir.quality.ocr_confidence,
                "warnings": ir.quality.parse_warnings,
                "blocks": len(ir.blocks),
                "chunks": len(chunks),
            },
        )
    )

    # Vector index (same embedder as query time).
    store.ensure_collection(collection, embedder.dim)
    vectors = embedder.embed([c.text for c in chunks]) if chunks else []
    acl_hash = _acl_hash({str(owner_id)} if owner_id else {"public"})
    points = []
    for c, vec in zip(chunks, vectors, strict=True):
        payload = ChunkPayload(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_version_id=version.id,
            section_id=c.section_id,
            toc_path=c.toc_path,
            page_no=c.page_no,
            bbox=c.bbox,
            keywords=[],
            entities=[],
            security_level=security_level,
            acl_hash=acl_hash,
            ocr_confidence=ir.quality.ocr_confidence,
            parser=ir.quality.parser,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )
        points.append((c.chunk_id, vec, payload.model_dump(mode="json")))
    if points:
        store.upsert(collection, points)

    session.commit()
    return ir.document_id, len(chunks)
