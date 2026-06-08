"""Chat endpoint (PRD2 §9 /api/chat).

The RAG pipeline and the caller's principals are FastAPI dependencies so they can be
overridden in tests and wired to real ingestion/auth later. Until ingestion populates a
corpus + index (E6/E9) and JWT auth lands (ADR-0005), the default pipeline dependency returns
503 — honest "not configured yet" rather than a fake-success.
"""

from __future__ import annotations

import hashlib
from typing import Annotated
from uuid import UUID

from db import AuditLog
from fastapi import APIRouter, Depends, HTTPException
from rag_core import RagPipeline
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal
from app.db import get_session
from app.rag import build_pipeline_from_db
from app.schemas import ChatRequest, ChatResponse, CitationOut

router = APIRouter(tags=["chat"])


def get_pipeline(session: Annotated[Session, Depends(get_session)]) -> RagPipeline:
    """Build the live pipeline from ingested data. 503 if the store is down or empty."""
    try:
        pipeline = build_pipeline_from_db(session)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="metadata store unavailable") from exc
    if not pipeline.corpus:
        raise HTTPException(status_code=503, detail="no documents ingested yet")
    return pipeline


def _actor_uuid(principal: Principal) -> UUID | None:
    try:
        return UUID(principal.sub)
    except (ValueError, AttributeError):
        return None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],  # auth gates first
    pipeline: Annotated[RagPipeline, Depends(get_pipeline)],
    session: Annotated[Session, Depends(get_session)],
) -> ChatResponse:
    principals = principal.as_set()
    scope_ids: set[UUID] | None = None
    if req.scope and req.scope.document_ids:
        scope_ids = {UUID(d) for d in req.scope.document_ids}

    result = pipeline.answer(
        req.message,
        principals=principals,
        mode=req.mode.value,
        model_hint=req.model_hint,
        scope_document_ids=scope_ids,
    )

    # Audit every model call at the choke point (ADR-0006). Message is hashed, not stored raw.
    session.add(
        AuditLog(
            actor_id=_actor_uuid(principal),
            action="chat",
            payload_hash=hashlib.sha256(req.message.encode("utf-8")).hexdigest()[:32],
        )
    )
    session.commit()
    return ChatResponse(
        answer=result.answer,
        citations=[
            CitationOut(
                document_id=str(c.document_id),
                chunk_id=c.chunk_id,
                page_no=c.page_no,
                section_path=c.section_path,
                source_span=c.source_span,
            )
            for c in result.citations
        ],
        confidence=result.confidence,
        warnings=result.warnings,
        retrieval_trace_id=result.retrieval_trace_id,
    )
