"""MarkItDown worker — DOCX/XLSX/PPTX/HTML/CSV/JSON/XML → Document IR (ADR-0007, PRD2 §5.2).

Office-only and complementary to OCR/HWPX. Maps Markdown onto canonical ``Block``s and
synthetically paginates at the shallowest heading level so every block keeps a 1-based
``page_no`` (the citation anchor). The MarkItDown call is isolated behind an injectable
converter (MD-001) so the mapping stays pure and testable without the binary.

Requirements: MD-001..005 (PRD2 §5.2). Epic E3. Output is validated against the shared IR
gate (``validate_ir``) before return — a worker must never emit invalid IR.
"""

from __future__ import annotations

from uuid import UUID

from document_ir import DocumentIR, DocumentType, Quality, validate_ir

from markitdown_worker.converter import MarkdownConverter, MarkItDownConverter
from markitdown_worker.mapper import markdown_to_blocks

__all__ = ["process", "MarkdownConverter", "MarkItDownConverter", "markdown_to_blocks"]

_PARSER_VERSION = "0.1.0"


def process(
    source_uri: str,
    document_id: UUID,
    *,
    document_type: DocumentType = DocumentType.DOCX,
    converter: MarkdownConverter | None = None,
    fallback: MarkdownConverter | None = None,
) -> DocumentIR:
    """Convert an Office/target file to validated Document IR.

    MD-005 fallback chain: if the primary converter raises and a ``fallback`` is provided,
    retry with it and flag ``used_fallback``. If everything fails, the error propagates.
    """
    converter = converter or MarkItDownConverter()
    warnings: list[str] = []
    used_fallback = False

    try:
        md = converter.convert(source_uri)
    except Exception as exc:  # noqa: BLE001 — surface the reason, then try fallback
        if fallback is None:
            raise
        warnings.append(f"primary converter failed ({exc!r}); used fallback")
        md = fallback.convert(source_uri)
        used_fallback = True

    mapped = markdown_to_blocks(md)
    warnings.extend(mapped.warnings)

    ir = DocumentIR(
        document_id=document_id,
        source_uri=source_uri,
        document_type=document_type,
        blocks=mapped.blocks,
        semantic_keywords=[],
        metadata={},
        quality=Quality(
            parser="markitdown",
            parser_version=_PARSER_VERSION,
            used_fallback=used_fallback,
            parse_warnings=warnings,
            extraction_coverage=mapped.extraction_coverage,
            table_preservation_score=mapped.table_preservation_score,
        ),
    )

    result = validate_ir(ir)
    if not result.ok:
        raise ValueError(f"markitdown produced invalid IR: {result.errors}")
    return ir
