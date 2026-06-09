"""Chat endpoint (PRD2 §9 /api/chat).

The RAG pipeline and the caller's principals are FastAPI dependencies so they can be
overridden in tests and wired to real ingestion/auth later. Until ingestion populates a
corpus + index (E6/E9) and JWT auth lands (ADR-0005), the default pipeline dependency returns
503 — honest "not configured yet" rather than a fake-success.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Annotated
from uuid import UUID

from db import AuditLog
from fastapi import APIRouter, Depends, HTTPException
from rag_core import RagPipeline
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal
from app.config import settings
from app.db import get_session
from app.rag import build_pipeline_from_db
from app.schemas import ChatRequest, ChatResponse, CitationOut


# Crockford base32 alphabet (no I/L/O/U) — ULID's encoding (RFC draft, 26 chars total).
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid() -> str:
    """ULID — 10 chars time (ms) + 16 chars randomness, lexicographically sortable.

    We avoid the `python-ulid` dep since we only need monotonic 26-char IDs in this one place.
    """
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = int.from_bytes(secrets.token_bytes(10), "big")
    val = (ts_ms << 80) | rand
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[val & 0x1F])
        val >>= 5
    return "".join(reversed(chars))

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

    t0 = time.monotonic()
    result = pipeline.answer(
        req.message,
        principals=principals,
        mode=req.mode.value,
        model_hint=req.model_hint,
        scope_document_ids=scope_ids,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)

    # Audit every model call at the choke point (ADR-0006). Message is hashed, not stored
    # raw. GP1 (ADR-0011 follow-up) adds event_id/trace_id/kind/outcome/metrics so the
    # Activity Logs and Audit Trail pages can surface per-call observability + later compare
    # model behavior pre/post Nemotron cutover.
    if result.warnings and "no claim survived" in " ".join(result.warnings):
        outcome = "dropped"
    elif result.citations:
        outcome = "ok"
    else:
        outcome = "dropped"
    session.add(
        AuditLog(
            actor_id=_actor_uuid(principal),
            action="chat",
            event_id=_ulid(),
            trace_id=result.retrieval_trace_id,
            kind="chat.request",
            outcome=outcome,
            metrics={
                "duration_ms": duration_ms,
                "model": settings.answer_model,
                "claims_supported": len(result.citations),
                "groundedness": result.confidence.get("groundedness"),
                "retrieval_quality": result.confidence.get("retrieval_quality"),
                "guardrails": result.guardrails,
                "warnings": result.warnings,
                "language": result.language,
            },
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
