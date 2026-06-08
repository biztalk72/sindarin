"""Upload + ingest endpoint (PRD2 §9 /api/upload).

MVP synchronous ingestion: routes the uploaded file by extension to the matching parser
worker, gets Document IR, then persists + indexes it (`app.ingest.ingest_ir`). Production
moves parsing to async workers off a queue (PRD2 §3); the route contract stays the same.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from document_ir import DocumentIR, DocumentType
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from rag_core import QdrantVectorStore
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal
from app.config import settings
from app.db import get_session
from app.ingest import ingest_ir
from app.rag import embedding_descriptor, select_embedder

router = APIRouter(tags=["ingest"], dependencies=[Depends(get_current_principal)])


def _owner_uuid(principal: Principal) -> UUID | None:
    try:
        return UUID(principal.sub)
    except (ValueError, AttributeError):
        return None

_EXT_TYPE = {
    ".docx": DocumentType.DOCX,
    ".xlsx": DocumentType.XLSX,
    ".pptx": DocumentType.PPTX,
    ".html": DocumentType.HTML,
    ".htm": DocumentType.HTML,
    ".csv": DocumentType.CSV,
    ".json": DocumentType.JSON,
    ".xml": DocumentType.XML,
    ".hwpx": DocumentType.HWPX,
    ".pdf": DocumentType.PDF,
}


def _parse(path: str, document_id: UUID, ext: str) -> DocumentIR:
    if ext == ".hwpx":
        from hwpx_worker import process as hwpx_process

        return hwpx_process(path, document_id)
    if ext == ".pdf":
        from ocr_worker import process as ocr_process
        from pypdf import PdfReader

        page_texts = [(p.extract_text() or "") for p in PdfReader(path).pages]
        return ocr_process(path, document_id, page_texts=page_texts)

    from markitdown_worker import process as md_process

    return md_process(path, document_id, document_type=_EXT_TYPE[ext])


@router.post("/upload")
async def upload(
    file: UploadFile,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _EXT_TYPE:
        raise HTTPException(status_code=415, detail=f"unsupported file type: {ext or '?'}")

    document_id = uuid4()
    data = await file.read()
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        tmp.write(data)
        tmp.close()
        try:
            ir = _parse(tmp.name, document_id, ext)
        except Exception as exc:  # noqa: BLE001 — surface parse failure as 422
            raise HTTPException(status_code=422, detail=f"parse failed: {exc}") from exc
    finally:
        os.unlink(tmp.name)

    model, version = embedding_descriptor(settings)
    doc_id, n_chunks = ingest_ir(
        ir,
        name=file.filename or str(document_id),
        session=session,
        embedder=select_embedder(settings),
        store=QdrantVectorStore(url=settings.vector_db_url),
        collection=settings.vector_collection,
        embedding_model=model,
        embedding_version=version,
        owner_id=_owner_uuid(principal),  # owner gets an ACL read grant (invariant #2)
    )
    return {"document_id": str(doc_id), "chunks": n_chunks, "status": "indexed"}
