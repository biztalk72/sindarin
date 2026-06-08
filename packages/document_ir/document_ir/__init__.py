"""Canonical Document IR — the single normalized contract every parser emits.

All preprocessing engines (MarkItDown, PaddleOCR/-VL, HWPX) must produce IR that validates
against these models (PRD2 §6.1). The IR feeds RAG retrieval, the PageIndex structure tree,
citations, UI navigation, and audit alike. The ``{document_id, page_no}`` pair is the
citation anchor and must survive end-to-end (invariant #3 / ADR-0004).
"""

from document_ir.models import (
    BBox,
    Block,
    BlockType,
    DocumentIR,
    DocumentType,
    Quality,
    SemanticKeyword,
    TableSchema,
)
from document_ir.validator import IRValidationResult, validate_ir

__all__ = [
    "BBox",
    "Block",
    "BlockType",
    "DocumentIR",
    "DocumentType",
    "Quality",
    "SemanticKeyword",
    "TableSchema",
    "IRValidationResult",
    "validate_ir",
]
