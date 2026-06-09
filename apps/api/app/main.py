"""FastAPI entrypoint. Mounts the PRD2 §9 routers under /api."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.auth import ensure_bootstrap_admin
from app.db import SessionLocal
from app.routers import admin, auth, chat, documents, dsr, health, upload


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Ensure the single-org bootstrap admin exists (ADR-0005). Best-effort; never blocks boot.
    with contextlib.suppress(Exception):
        session = SessionLocal()
        try:
            ensure_bootstrap_admin(session)
        finally:
            session.close()
    yield


app = FastAPI(title="Hybrid IDP API", version="0.0.0", lifespan=lifespan)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(dsr.router, prefix="/api")
app.include_router(dsr.admin_router, prefix="/api")

# TODO (PRD2 §9, by epic):
#   /api/upload, /api/documents[...]            E9 UI core / ingest
#   /api/documents/{id}/{toc,keywords,graph}    E10 UI insight
#   /api/ingest/jobs/{id}[/retry]               E6 indexing
#   /api/chat, /api/chat/{id}/feedback          E7 RAG
#   /api/admin/health, /api/eval/run            E11 admin / E8 trust
# All document/keyword/graph/citation routers must pass the same ACL middleware (PRD2 §9).
