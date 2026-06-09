"""Data-subject requests (GP4 / D2).

Two surfaces share this module:
  - **user** (authenticated): create their own export/forget request; list their own.
  - **admin**: list all pending requests; mark them completed. The actual export bundle
    in D2 is metadata-only (counts of each personal-data class); the actual forget
    anonymises audit_logs.actor_id, tombstones the user's email, drops their ACL rows.
    Wider forget paths (document deletion / vector index scrub) belong to the retention
    workers — out of scope here.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from typing import Annotated, Any

from db import AclEntry, AuditLog, Document, DsrRequest, User
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal, require_roles
from app.db import get_session

router = APIRouter(tags=["dsr"], dependencies=[Depends(get_current_principal)])


class DsrCreate(BaseModel):
    kind: str = Field(pattern="^(export|forget)$")
    scope: dict[str, Any] | None = None


def _row_dict(d: DsrRequest) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "kind": d.kind,
        "status": d.status,
        "requester_id": str(d.requester_id),
        "scope": d.scope,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "processed_at": d.processed_at.isoformat() if d.processed_at else None,
        "processed_by": str(d.processed_by) if d.processed_by else None,
        "result": d.result,
    }


def _actor_uuid(principal: Principal) -> uuid.UUID:
    try:
        return uuid.UUID(principal.sub)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="invalid actor") from exc


# --- user-facing -------------------------------------------------------------------

@router.get("/dsr/me")
def list_my_requests(
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> list[dict[str, Any]]:
    actor = _actor_uuid(principal)
    rows = session.execute(
        select(DsrRequest)
        .where(DsrRequest.requester_id == actor)
        .order_by(DsrRequest.created_at.desc())
        .limit(50)
    ).scalars().all()
    return [_row_dict(r) for r in rows]


@router.post("/dsr")
def create_request(
    body: Annotated[DsrCreate, Body()],
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    actor = _actor_uuid(principal)
    row = DsrRequest(requester_id=actor, kind=body.kind, scope=body.scope, status="pending")
    session.add(row)
    session.add(AuditLog(
        actor_id=actor, action="dsr.create", kind="dsr.request", outcome="ok",
        metrics={"dsr_kind": body.kind},
    ))
    session.commit()
    session.refresh(row)
    return _row_dict(row)


# --- admin -------------------------------------------------------------------------

admin_router = APIRouter(tags=["admin"], dependencies=[Depends(require_roles("admin"))])


@admin_router.get("/admin/dsr")
def admin_list_requests(
    session: Annotated[Session, Depends(get_session)],
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    q = select(DsrRequest).order_by(DsrRequest.created_at.desc()).limit(limit)
    if status:
        q = q.where(DsrRequest.status == status)
    rows = session.execute(q).scalars().all()
    return [_row_dict(r) for r in rows]


def _run_export(session: Session, requester_id: uuid.UUID) -> dict[str, Any]:
    """D2 export = metadata-only summary (counts of each personal-data class).

    A full ZIP/JSON dump streaming endpoint is a follow-up. Today the requester sees an
    immediate transparency report — exactly which audit rows and which owned documents
    the platform considers theirs — and admin can pair this with a follow-up 'forget' to
    clear them.
    """
    audit_rows = session.execute(
        select(AuditLog).where(AuditLog.actor_id == requester_id)
    ).scalars().all()
    docs = session.execute(
        select(Document).where(Document.owner_id == requester_id)
    ).scalars().all()
    return {
        "audit_log_count": len(audit_rows),
        "owned_documents": [{"id": str(d.id), "name": d.name} for d in docs],
    }


def _run_forget(session: Session, requester_id: uuid.UUID) -> dict[str, Any]:
    """D2 forget = anonymise audit rows + tombstone user + drop ACL grants.

    Audit rows survive (regulatory requirement) but lose the actor pointer; the user's
    email becomes a deterministic tombstone hash so the row can't be re-resolved. Wider
    cleanup (their documents, vector chunks, retention) is the retention worker's job —
    not stuffed into the request path."""
    session.execute(
        update(AuditLog).where(AuditLog.actor_id == requester_id).values(actor_id=None)
    )
    tombstone = "tombstone-" + hashlib.sha256(str(requester_id).encode()).hexdigest()[:16]
    session.execute(
        update(User).where(User.id == requester_id).values(email=tombstone, password_hash=None)
    )
    acl_deleted = session.execute(
        delete(AclEntry).where(AclEntry.principal_id == requester_id)
    ).rowcount
    return {
        "audit_actor_cleared": True,
        "user_tombstoned": True,
        "acl_entries_dropped": int(acl_deleted or 0),
    }


@admin_router.post("/admin/dsr/{request_id}/process")
def admin_process(
    request_id: str,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    try:
        rid = uuid.UUID(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid request id") from exc
    row = session.get(DsrRequest, rid)
    if row is None:
        raise HTTPException(status_code=404, detail="dsr request not found")
    if row.status not in {"pending", "processing"}:
        raise HTTPException(status_code=409, detail=f"already {row.status}")
    row.status = "processing"
    session.flush()

    if row.kind == "export":
        result = _run_export(session, row.requester_id)
    elif row.kind == "forget":
        result = _run_forget(session, row.requester_id)
    else:
        raise HTTPException(status_code=400, detail=f"unsupported kind {row.kind}")

    row.status = "completed"
    row.processed_at = dt.datetime.now(tz=dt.timezone.utc)
    row.processed_by = _actor_uuid(principal)
    row.result = result
    session.add(AuditLog(
        actor_id=row.processed_by,
        action=f"dsr.process.{row.kind}",
        kind="dsr.request",
        outcome="ok",
        resource_id=row.id,
        metrics=result,
    ))
    session.commit()
    session.refresh(row)
    return _row_dict(row)
