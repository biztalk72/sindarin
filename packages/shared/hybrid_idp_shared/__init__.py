"""Shared primitives used by apps/api and workers."""

from enum import StrEnum


class Role(StrEnum):
    """User roles (PRD2 §2.4 / ADR-0005, widened by ADR-0010)."""

    ADMIN = "admin"
    DOCUMENT_MANAGER = "document_manager"
    AUDITOR = "auditor"
    USER = "user"


class SecurityLevel(StrEnum):
    """Document security label (PRD2 §6.2 ``documents.security_level``)."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class IngestionStage(StrEnum):
    """Ingestion job stages surfaced as UI status badges (PRD2 §8.2 UI-DOC-002)."""

    UPLOADED = "uploaded"
    PREPROCESSING = "preprocessing"
    OCR = "ocr"
    KEYWORDS = "keywords"
    INDEXED = "indexed"
    ERROR = "error"
    NEEDS_REPROCESS = "needs_reprocess"


__all__ = ["Role", "SecurityLevel", "IngestionStage"]
