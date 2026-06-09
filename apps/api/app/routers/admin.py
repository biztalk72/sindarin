"""Admin observability (E11, PRD2 §9 /api/admin, §10.3). Admin-only (ADR-0005):
component health, aggregate metrics, ingestion jobs (+ parser warnings), recent audit log.
"""

from __future__ import annotations

import json
import os
from datetime import date as date_t, datetime
from pathlib import Path
from typing import Annotated, Any

import datetime as dt
import uuid

from db import AuditLog, Document, DocumentChunk, GuardrailOverride, IngestionJob, User
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal, require_roles
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


class OverrideCreate(BaseModel):
    kind: str = Field(pattern="^(pii|injection)$")
    policy_name: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=8, max_length=1000)  # 8+ chars enforces "say something useful"
    ttl_minutes: int | None = Field(default=60, ge=1, le=60 * 24)


def _override_dict(o: GuardrailOverride) -> dict[str, Any]:
    now = dt.datetime.now(tz=dt.timezone.utc)
    active = o.revoked_at is None and (o.expires_at is None or o.expires_at > now)
    return {
        "id": str(o.id),
        "kind": o.kind,
        "policy_name": o.policy_name,
        "reason": o.reason,
        "created_by": str(o.created_by),
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "expires_at": o.expires_at.isoformat() if o.expires_at else None,
        "revoked_at": o.revoked_at.isoformat() if o.revoked_at else None,
        "revoked_by": str(o.revoked_by) if o.revoked_by else None,
        "active": active,
    }


@router.get("/admin/guardrails/overrides")
def admin_overrides_list(
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    q = select(GuardrailOverride).order_by(GuardrailOverride.created_at.desc()).limit(limit)
    if active_only:
        now = dt.datetime.now(tz=dt.timezone.utc)
        q = q.where(
            GuardrailOverride.revoked_at.is_(None),
            (GuardrailOverride.expires_at.is_(None)) | (GuardrailOverride.expires_at > now),
        )
    rows = session.execute(q).scalars().all()
    return [_override_dict(o) for o in rows]


@router.post("/admin/guardrails/overrides")
def admin_overrides_create(
    body: Annotated[OverrideCreate, Body()],
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    """Record an override intent. Audit-only in D1 — runtime apply lands in D1b."""
    try:
        actor = uuid.UUID(principal.sub)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="invalid actor") from exc
    expires_at: dt.datetime | None = None
    if body.ttl_minutes is not None:
        expires_at = dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(minutes=body.ttl_minutes)
    row = GuardrailOverride(
        kind=body.kind,
        policy_name=body.policy_name,
        reason=body.reason,
        created_by=actor,
        expires_at=expires_at,
    )
    session.add(row)
    # Also write the override intent into the audit log so it appears on the Audit Trail
    # alongside chat.requests — single audit surface for any reviewer.
    session.add(
        AuditLog(
            actor_id=actor,
            action="guardrail.override.create",
            kind="guardrail.override",
            outcome="ok",
            metrics={
                "policy_kind": body.kind,
                "policy_name": body.policy_name,
                "ttl_minutes": body.ttl_minutes,
                "reason_chars": len(body.reason),
            },
        )
    )
    session.commit()
    session.refresh(row)
    return _override_dict(row)


@router.delete("/admin/guardrails/overrides/{override_id}")
def admin_overrides_revoke(
    override_id: str,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    try:
        oid = uuid.UUID(override_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid override id") from exc
    row = session.get(GuardrailOverride, oid)
    if row is None:
        raise HTTPException(status_code=404, detail="override not found")
    if row.revoked_at is None:
        row.revoked_at = dt.datetime.now(tz=dt.timezone.utc)
        try:
            row.revoked_by = uuid.UUID(principal.sub)
        except (ValueError, AttributeError):
            pass
        session.add(
            AuditLog(
                actor_id=row.revoked_by,
                action="guardrail.override.revoke",
                kind="guardrail.override",
                outcome="ok",
                resource_id=row.id,
            )
        )
        session.commit()
        session.refresh(row)
    return _override_dict(row)


@router.get("/admin/guardrails/policies")
def admin_guardrails_policies() -> dict[str, Any]:
    """Read-only inventory of active guardrail patterns (GP3). Code-loaded today; the GP4
    DB-loaded policies story replaces this body but the contract stays stable."""
    from rag_core import list_injection_policies, list_pii_policies

    return {
        "pii": list_pii_policies(),
        "injection": list_injection_policies(),
    }


@router.get("/admin/guardrails/events")
def admin_guardrails_events(
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Recent guardrail activity surfaced from audit_logs.metrics.guardrails (GP3).

    No new table yet — we project from existing observability. A future GP4 will move the
    raw events into a dedicated `guardrail_events` row when override / approval workflows
    need them as first-class records.
    """
    rows = (
        session.execute(
            select(AuditLog)
            .where(AuditLog.kind == "chat.request")
            .order_by(AuditLog.created_at.desc())
            .limit(limit * 4)  # over-fetch then filter — most rows have zero hits
        )
        .scalars()
        .all()
    )
    out: list[dict[str, Any]] = []
    for a in rows:
        g = (a.metrics or {}).get("guardrails") if a.metrics else None
        if not isinstance(g, dict):
            continue
        hits = (
            int(g.get("input_pii", 0) or 0)
            + int(g.get("injection_removed", 0) or 0)
            + int(g.get("output_pii", 0) or 0)
        )
        if hits == 0:
            continue
        out.append({
            "event_id": a.event_id,
            "trace_id": a.trace_id,
            "actor_id": str(a.actor_id) if a.actor_id else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "input_pii": int(g.get("input_pii", 0) or 0),
            "injection_removed": int(g.get("injection_removed", 0) or 0),
            "output_pii": int(g.get("output_pii", 0) or 0),
        })
        if len(out) >= limit:
            break
    return out


@router.get("/admin/compliance/summary")
def admin_compliance_summary(
    session: Annotated[Session, Depends(get_session)],
    from_date: Annotated[str | None, Query(alias="from")] = None,
    to_date: Annotated[str | None, Query(alias="to")] = None,
) -> dict[str, Any]:
    """Aggregate counters for the Compliance Report card (GP4 D3).

    Time window defaults to last 30 days. `from` / `to` are ISO YYYY-MM-DD; both inclusive.
    Returns scalar counts + outcome / model / kind histograms — same numbers the CSV export
    serialises row-by-row.
    """
    end = dt.datetime.fromisoformat(to_date) if to_date else dt.datetime.now(tz=dt.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=dt.timezone.utc)
    start = (
        dt.datetime.fromisoformat(from_date) if from_date else end - dt.timedelta(days=30)
    )
    if start.tzinfo is None:
        start = start.replace(tzinfo=dt.timezone.utc)

    rows = session.execute(
        select(AuditLog).where(AuditLog.created_at >= start, AuditLog.created_at <= end)
    ).scalars().all()

    by_kind: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    by_model: dict[str, int] = {}
    guardrail_total = {"input_pii": 0, "injection_removed": 0, "output_pii": 0}
    durations: list[int] = []
    cited = 0
    dropped = 0

    for r in rows:
        k = r.kind or r.action or "unknown"
        by_kind[k] = by_kind.get(k, 0) + 1
        if r.outcome:
            by_outcome[r.outcome] = by_outcome.get(r.outcome, 0) + 1
        m = (r.metrics or {}).get("model")
        if isinstance(m, str):
            by_model[m] = by_model.get(m, 0) + 1
        g = (r.metrics or {}).get("guardrails")
        if isinstance(g, dict):
            for key in guardrail_total:
                v = g.get(key, 0)
                if isinstance(v, (int, float)):
                    guardrail_total[key] += int(v)
        d = (r.metrics or {}).get("duration_ms")
        if isinstance(d, (int, float)):
            durations.append(int(d))
        cs = (r.metrics or {}).get("claims_supported")
        if isinstance(cs, (int, float)):
            if cs > 0:
                cited += 1
            elif r.outcome == "dropped":
                dropped += 1

    durations.sort()
    n = len(durations)
    p50 = durations[n // 2] if n else None
    p95 = durations[int(n * 0.95)] if n else None

    return {
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "total_events": len(rows),
        "by_kind": by_kind,
        "by_outcome": by_outcome,
        "by_model": by_model,
        "guardrails_hits_total": guardrail_total,
        "chat": {"cited_count": cited, "dropped_count": dropped, "p50_ms": p50, "p95_ms": p95},
    }


@router.get("/admin/compliance/audit.csv")
def admin_compliance_csv(
    session: Annotated[Session, Depends(get_session)],
    from_date: Annotated[str | None, Query(alias="from")] = None,
    to_date: Annotated[str | None, Query(alias="to")] = None,
):  # FastAPI handles Response streaming via fastapi.responses
    """CSV export of audit_logs over the given window. One row per AuditLog row.

    Note: returns text/csv with the GP1 observability columns. PDF export with charts
    is a follow-up that needs a heavier dep (reportlab / weasyprint) — explicitly deferred.
    """
    from fastapi.responses import StreamingResponse
    import csv
    import io

    end = dt.datetime.fromisoformat(to_date) if to_date else dt.datetime.now(tz=dt.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=dt.timezone.utc)
    start = (
        dt.datetime.fromisoformat(from_date) if from_date else end - dt.timedelta(days=30)
    )
    if start.tzinfo is None:
        start = start.replace(tzinfo=dt.timezone.utc)

    rows = session.execute(
        select(AuditLog)
        .where(AuditLog.created_at >= start, AuditLog.created_at <= end)
        .order_by(AuditLog.created_at)
    ).scalars().all()

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([
            "created_at", "event_id", "trace_id", "kind", "action", "outcome",
            "actor_id", "resource_id",
            "duration_ms", "model", "language", "claims_supported", "groundedness",
            "input_pii", "injection_removed", "output_pii", "warnings",
        ])
        yield buf.getvalue(); buf.seek(0); buf.truncate(0)

        for r in rows:
            m = r.metrics or {}
            g = m.get("guardrails") or {}
            w.writerow([
                r.created_at.isoformat() if r.created_at else "",
                r.event_id or "",
                r.trace_id or "",
                r.kind or "",
                r.action or "",
                r.outcome or "",
                str(r.actor_id) if r.actor_id else "",
                str(r.resource_id) if r.resource_id else "",
                m.get("duration_ms", ""),
                m.get("model", ""),
                m.get("language", ""),
                m.get("claims_supported", ""),
                m.get("groundedness", ""),
                g.get("input_pii", "") if isinstance(g, dict) else "",
                g.get("injection_removed", "") if isinstance(g, dict) else "",
                g.get("output_pii", "") if isinstance(g, dict) else "",
                "|".join(m.get("warnings") or []) if isinstance(m.get("warnings"), list) else "",
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    fname = f"compliance-{start.date().isoformat()}-to-{end.date().isoformat()}.csv"
    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/admin/compliance/egress")
def admin_compliance_egress() -> dict[str, Any]:
    """External-egress sentinel (GP3). The platform invariant is "no data leaves the node"
    (`docs/runbooks/go-live.md` Option B); this surfaces whether the live model base URLs
    point inside the GB10 compose network or not. Visible to anyone admin via a top-bar
    banner when `external=true`."""
    chat_url = settings.openai_base_url or ""
    embed_url = settings.embedding_base_url or chat_url
    # In-network URLs look like http://vllm-chat:8000/v1 — non-routable hostname starts with
    # the service name. External URLs typically resolve to a public domain.
    def _is_in_network(u: str) -> bool:
        return any(host in u for host in ("vllm-chat", "vllm-embed", "localhost", "127.0.0.1"))

    chat_in = _is_in_network(chat_url)
    embed_in = _is_in_network(embed_url)
    return {
        "external": not (chat_in and embed_in),
        "chat":  {"url": chat_url,  "in_network": chat_in},
        "embed": {"url": embed_url, "in_network": embed_in},
    }


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
