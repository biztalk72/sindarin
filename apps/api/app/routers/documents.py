"""Document list + insight + ingestion job status (PRD2 §9). All routes require a valid token
(ADR-0005) and are ACL-scoped to the caller (invariant #2): admin sees all; others see only
documents they own or have an ACL grant for.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from db import Document, DocumentBlock, DocumentChunk, DocumentKeyword, IngestionJob
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal
from app.db import get_session
from app.insight import build_graph, build_toc, compute_keywords
from app.repository import PostgresAuthorizer
from app.schemas import DocumentOut, JobOut

# Router-level dependency enforces auth on every route here.
router = APIRouter(tags=["documents"], dependencies=[Depends(get_current_principal)])


def _chunk_rows(session: Session, document_id: UUID) -> list[DocumentChunk]:
    return list(
        session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.page_no)
        )
        .scalars()
        .all()
    )


def _authorized_or_404(session: Session, document_id: UUID, principal: Principal) -> Document:
    """Return the document iff the principal may read it; else 404 (don't leak existence)."""
    allowed = PostgresAuthorizer(session).allowed_documents(principal.as_set())
    doc = session.get(Document, document_id)
    if doc is None or (allowed is not None and document_id not in allowed):
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@router.get("/documents")
def list_documents(
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> list[DocumentOut]:
    allowed = PostgresAuthorizer(session).allowed_documents(principal.as_set())
    counts: dict[UUID, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(DocumentChunk.document_id, func.count()).group_by(DocumentChunk.document_id)
        ).all()
    }
    query = select(Document).order_by(Document.created_at.desc())
    if allowed is not None:  # non-admin: restrict to permitted documents
        query = query.where(Document.id.in_(allowed))
    docs = session.execute(query).scalars().all()
    return [
        DocumentOut(
            id=str(d.id),
            name=d.name,
            type=d.type,
            status=d.status,
            security_level=d.security_level,
            created_at=d.created_at.isoformat() if d.created_at else None,
            chunk_count=counts.get(d.id, 0),
        )
        for d in docs
    ]


@router.get("/ingest/jobs/{job_id}")
def get_job(job_id: UUID, session: Annotated[Session, Depends(get_session)]) -> JobOut:
    job = session.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobOut(
        id=str(job.id), document_id=str(job.document_id), stage=job.stage, status=job.status
    )


# --- Document insight (E10, PRD2 §8.3 / §9) ---


@router.get("/documents/{document_id}/toc")
def get_toc(
    document_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    _authorized_or_404(session, document_id, principal)
    # Build from blocks (full section_path per block, in document order) so nested headings
    # survive — chunk toc_path only carries the lead block's path.
    blocks = (
        session.execute(
            select(DocumentBlock)
            .where(DocumentBlock.document_id == document_id)
            .order_by(DocumentBlock.seq)
        )
        .scalars()
        .all()
    )
    items = [(list(b.section_path or []), b.page_no) for b in blocks if b.section_path]
    return {"toc_tree": build_toc(items)}


@router.get("/documents/{document_id}/keywords")
def get_keywords(
    document_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    _authorized_or_404(session, document_id, principal)
    texts = [r.text for r in _chunk_rows(session, document_id)]
    persisted: list[tuple[str, float | None, str | None]] = [
        (k.keyword, k.weight, None)
        for k in session.execute(
            select(DocumentKeyword).where(DocumentKeyword.document_id == document_id)
        )
        .scalars()
        .all()
    ]
    return {"keywords": compute_keywords(texts, persisted)}


@router.get("/documents/{document_id}/graph")
def get_graph(
    document_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    _authorized_or_404(session, document_id, principal)
    texts = [r.text for r in _chunk_rows(session, document_id)]
    top = [k["keyword"] for k in compute_keywords(texts)]
    return build_graph(texts, top)


@router.get("/documents/{document_id}/quality")
def get_quality(
    document_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    """Quality + metadata panel (UI-DOC-003): parser, coverage, OCR confidence, warnings."""
    doc = _authorized_or_404(session, document_id, principal)
    job = (
        session.execute(
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    return {
        "document_id": str(document_id),
        "name": doc.name,
        "type": doc.type,
        "security_level": doc.security_level,
        "status": job.status if job else "unknown",
        "metrics": (job.metrics if job and job.metrics else {}),
    }


@router.get("/documents/{document_id}/preview")
def get_preview(
    document_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    """Source preview: blocks in document order (PRD2 §9). No page images yet — text + bbox +
    block_ref so the UI can scroll-to / highlight a cited block."""
    doc = _authorized_or_404(session, document_id, principal)
    blocks = (
        session.execute(
            select(DocumentBlock)
            .where(DocumentBlock.document_id == document_id)
            .order_by(DocumentBlock.seq)
        )
        .scalars()
        .all()
    )
    return {
        "document_id": str(document_id),
        "name": doc.name,
        "type": doc.type,
        "blocks": [
            {
                "block_ref": b.block_ref,
                "page_no": b.page_no,
                "block_type": b.block_type,
                "text": b.text,
                "section_path": list(b.section_path or []),
                "bbox": b.bbox,
            }
            for b in blocks
        ],
    }
