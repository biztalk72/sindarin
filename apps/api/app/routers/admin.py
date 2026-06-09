"""Admin observability (E11, PRD2 §9 /api/admin, §10.3). Admin-only (ADR-0005):
component health, aggregate metrics, ingestion jobs (+ parser warnings), recent audit log.
"""

from __future__ import annotations

import json
import os
from datetime import date as date_t, datetime
from pathlib import Path
from typing import Annotated, Any

from db import AuditLog, Document, DocumentChunk, IngestionJob, User
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.config import settings
from app.db import get_session
from app.rag import openai_configured

# Every route requires the admin role.
router = APIRouter(tags=["admin"], dependencies=[Depends(require_roles("admin"))])


def _check_postgres(session: Session) -> str:
    try:
        session.execute(text("SELECT 1"))
        return "ok"
    except Exception:  # noqa: BLE001
        return "error"


def _check_vector_db() -> str:
    try:
        from rag_core import QdrantVectorStore

        QdrantVectorStore(url=settings.vector_db_url)._c().get_collections()
        return "ok"
    except Exception:  # noqa: BLE001
        return "error"


@router.get("/admin/health")
def admin_health(session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    pg = _check_postgres(session)
    vec = _check_vector_db()
    components = {
        "postgres": pg,
        "vector_db": vec,
        "model_endpoint": "configured" if openai_configured() else "dev-mode",
    }
    overall = "ok" if pg == "ok" and vec == "ok" else "degraded"
    return {"status": overall, "components": components}


@router.get("/admin/metrics")
def admin_metrics(session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    def count(model: type[Any]) -> int:
        return int(session.execute(select(func.count()).select_from(model)).scalar_one())

    jobs_by_status: dict[str, int] = {
        row[0]: row[1]
        for row in session.execute(
            select(IngestionJob.status, func.count()).group_by(IngestionJob.status)
        ).all()
    }
    return {
        "documents": count(Document),
        "chunks": count(DocumentChunk),
        "users": count(User),
        "audit_events": count(AuditLog),
        "ingestion_jobs": {str(k): int(v) for k, v in jobs_by_status.items()},
        "host": {"cpu_count": os.cpu_count()},
        # GB10 unified-memory / GPU / thermal telemetry requires the node's NVIDIA tooling
        # (PRD2 §10.3) — surfaced as a collector on the GB10 host, not available here.
        "gb10_telemetry": "unavailable (collect on the GB10 node)",
    }


@router.get("/admin/jobs")
def admin_jobs(
    session: Annotated[Session, Depends(get_session)], limit: int = 50
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(IngestionJob, Document.name)
        .join(Document, Document.id == IngestionJob.document_id, isouter=True)
        .order_by(IngestionJob.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(job.id),
            "document_id": str(job.document_id),
            "document_name": name,
            "stage": job.stage,
            "status": job.status,
            "metrics": job.metrics or {},
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
        for job, name in rows
    ]


@router.get("/admin/logs/files")
def admin_logs_files() -> list[str]:
    """Available daily-overlap log files (GP2). Returns dates, newest first."""
    log_dir = Path(os.environ.get("EVENTS_LOG_DIR", "/srv/var/log/hybrid-idp"))
    if not log_dir.is_dir():
        return []
    dates: list[str] = []
    for p in sorted(log_dir.glob("events-*.jsonl"), reverse=True):
        name = p.name.removeprefix("events-").removesuffix(".jsonl")
        try:
            date_t.fromisoformat(name)
        except ValueError:
            continue
        dates.append(name)
    return dates


@router.get("/admin/logs/by-date")
def admin_logs_by_date(
    log_date: Annotated[str, Query(alias="date")],
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Read one daily log file. ``date`` must be ISO ``YYYY-MM-DD``; ``limit`` caps lines."""
    try:
        d = date_t.fromisoformat(log_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be ISO YYYY-MM-DD") from exc
    log_dir = Path(os.environ.get("EVENTS_LOG_DIR", "/srv/var/log/hybrid-idp"))
    f = log_dir / f"events-{d.isoformat()}.jsonl"
    if not f.is_file():
        return []
    out: list[dict[str, Any]] = []
    with f.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # Newest first; clamp to limit. Sort key tolerates pre-GP2 rows that lack `ts`.
    out.sort(key=lambda r: r.get("ts") or "", reverse=True)
    return out[:limit]


@router.get("/admin/audit")
def admin_audit(
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
    kind: str | None = None,
    outcome: str | None = None,
) -> list[dict[str, Any]]:
    # Optional filters (kind=chat.request, outcome=ok|dropped|error|...) — added with GP1
    # so the new Activity Logs and Audit Trail pages can drill into specific event types.
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if kind:
        q = q.where(AuditLog.kind == kind)
    if outcome:
        q = q.where(AuditLog.outcome == outcome)
    rows = session.execute(q).scalars().all()
    return [
        {
            "action": a.action,
            "actor_id": str(a.actor_id) if a.actor_id else None,
            "payload_hash": a.payload_hash,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "event_id": a.event_id,
            "trace_id": a.trace_id,
            "kind": a.kind,
            "outcome": a.outcome,
            "metrics": a.metrics or {},
        }
        for a in rows
    ]
