"""Embedding worker — chunk → embed → write to vector DB (E6, ADR-0008).

Chunks Document IR, embeds via an injectable ``Embedder`` (batched, with retry), and upserts
each chunk with the full ``ChunkPayload`` contract (PRD2 §6.3) so ACL filter, citation, and
blue/green reindex all work off the store. Collections are versioned by ``embedding_version``
(``{base}__{version}``); ``activate`` flips the serving alias (blue/green).

Embedding-model choice is a deferred follow-up ADR (PRD2 §15).
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable, Iterator
from typing import Any
from uuid import UUID

from document_ir import DocumentIR
from hybrid_idp_shared import SecurityLevel
from rag_core import Chunk, ChunkPayload, Embedder, VectorStore, chunk_document

__all__ = ["index", "collection_name", "activate", "acl_hash_for"]


def collection_name(base: str, embedding_version: str) -> str:
    return f"{base}__{embedding_version}"


def acl_hash_for(principals: Iterable[str]) -> str:
    """Stable hash of the principals allowed to see a document (payload ACL token)."""
    joined = ",".join(sorted(set(principals)))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


def _batches(items: list[Any], size: int) -> Iterator[list[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _embed_with_retry(
    embedder: Embedder, texts: list[str], *, max_retries: int
) -> list[list[float]]:
    attempt = 0
    while True:
        try:
            return embedder.embed(texts)
        except Exception:  # noqa: BLE001 — transient embedding-endpoint errors
            attempt += 1
            if attempt > max_retries:
                raise
            time.sleep(0)  # placeholder backoff; real backoff wired with the endpoint


def index(
    ir: DocumentIR,
    *,
    embedder: Embedder,
    store: VectorStore,
    base_collection: str,
    embedding_model: str,
    embedding_version: str,
    security_level: SecurityLevel,
    acl_hash: str,
    document_version_id: UUID | None = None,
    batch_size: int = 64,
    max_retries: int = 3,
) -> list[ChunkPayload]:
    """Chunk + embed + upsert ``ir`` into the versioned collection. Returns the payloads."""
    chunks: list[Chunk] = chunk_document(ir)
    name = collection_name(base_collection, embedding_version)
    store.ensure_collection(name, embedder.dim)

    payloads: list[ChunkPayload] = []
    points: list[tuple[str, list[float], dict[str, Any]]] = []

    for batch in _batches(chunks, batch_size):
        vectors = _embed_with_retry(embedder, [c.text for c in batch], max_retries=max_retries)
        for chunk, vec in zip(batch, vectors, strict=True):
            payload = ChunkPayload(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_version_id=document_version_id or chunk.document_id,
                section_id=chunk.section_id,
                toc_path=chunk.toc_path,
                page_no=chunk.page_no,
                bbox=chunk.bbox,
                keywords=[],
                entities=[],
                security_level=security_level,
                acl_hash=acl_hash,
                ocr_confidence=ir.quality.ocr_confidence,
                parser=ir.quality.parser,
                embedding_model=embedding_model,
                embedding_version=embedding_version,
            )
            payloads.append(payload)
            points.append((chunk.chunk_id, vec, payload.model_dump(mode="json")))

    if points:
        store.upsert(name, points)
    return payloads


def activate(
    store: VectorStore, *, alias: str, base_collection: str, embedding_version: str
) -> None:
    """Blue/green: point the serving alias at the freshly-indexed versioned collection."""
    store.set_alias(alias, collection_name(base_collection, embedding_version))
