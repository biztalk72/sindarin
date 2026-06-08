"""Relational metadata store — SQLAlchemy 2.0 models (PRD2 §6.2).

Postgres is the system of record for document metadata, users/ACL, ingestion jobs, audit
logs, and eval runs. The IR block store here mirrors ``document_ir`` fields; the vector DB
(ADR-0008) holds the searchable chunks. ``Base.metadata`` is the Alembic autogenerate target
(see ``infra/migrations``).

Enum-like columns (role, security_level, status, permission) are stored as strings using the
values from ``hybrid_idp_shared`` rather than native PG enums, to keep migrations simple.
"""

from db.base import Base
from db.models import (
    AclEntry,
    AuditLog,
    Document,
    DocumentBlock,
    DocumentChunk,
    DocumentEntity,
    DocumentKeyword,
    DocumentTable,
    DocumentVersion,
    EvalRun,
    IngestionJob,
    KeywordEdge,
    User,
)

__all__ = [
    "Base",
    "User",
    "Document",
    "DocumentVersion",
    "DocumentBlock",
    "DocumentChunk",
    "DocumentTable",
    "DocumentKeyword",
    "DocumentEntity",
    "KeywordEdge",
    "IngestionJob",
    "AclEntry",
    "AuditLog",
    "EvalRun",
]
