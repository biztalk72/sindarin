"""Re-embed the persisted corpus into a (new) vector collection — the dev→live switch tool.

Switching embedders (dev deterministic dim 64 → a real model, e.g. dim 1536) changes the
vector space, so every chunk must be re-embedded. This loads all `document_chunks` from
Postgres, embeds them with the currently-configured embedder, and upserts into
`settings.vector_collection`. Blue/green: point `VECTOR_COLLECTION` at a NEW name, reindex,
then restart the api (and ingestion writes there too).

Run: `make reindex`  (or `uv run python -m app.reindex`).
"""

from __future__ import annotations

import hashlib
from typing import Any

from db import DocumentChunk
from document_ir import BBox
from hybrid_idp_shared import SecurityLevel
from rag_core import ChunkPayload, Embedder, VectorStore
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.db import SessionLocal
from app.rag import embedding_descriptor, select_embedder


def reindex_corpus(
    session: Session,
    *,
    embedder: Embedder,
    store: VectorStore,
    collection: str,
    embedding_model: str,
    embedding_version: str,
    batch_size: int = 128,
) -> int:
    """Re-embed all persisted chunks into ``collection``. Returns the number indexed."""
    chunks = list(session.execute(select(DocumentChunk)).scalars().all())
    if not chunks:
        return 0

    store.ensure_collection(collection, embedder.dim)
    total = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vectors = embedder.embed([c.text for c in batch])
        points: list[tuple[str, list[float], dict[str, Any]]] = []
        for c, vec in zip(batch, vectors, strict=True):
            try:
                sec = SecurityLevel(c.security_level)
            except ValueError:
                sec = SecurityLevel.INTERNAL
            payload = ChunkPayload(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_version_id=c.document_version_id or c.document_id,
                section_id=c.section_id,
                toc_path=list(c.toc_path or []),
                page_no=c.page_no,
                bbox=BBox(**c.bbox) if c.bbox else None,
                keywords=[],
                entities=[],
                security_level=sec,
                acl_hash=hashlib.sha256(b"reindex").hexdigest()[:32],
                parser="reindex",
                embedding_model=embedding_model,
                embedding_version=embedding_version,
            )
            points.append((c.chunk_id, vec, payload.model_dump(mode="json")))
        store.upsert(collection, points)
        total += len(points)
    return total


def main(s: Settings = settings) -> None:
    from rag_core import QdrantVectorStore

    model, version = embedding_descriptor(s)
    embedder = select_embedder(s)
    with SessionLocal() as session:
        n = reindex_corpus(
            session,
            embedder=embedder,
            store=QdrantVectorStore(url=s.vector_db_url),
            collection=s.vector_collection,
            embedding_model=model,
            embedding_version=version,
        )
    print(
        f"reindexed {n} chunks → collection '{s.vector_collection}' "
        f"(model={model} dim={embedder.dim})"
    )


if __name__ == "__main__":
    main()
