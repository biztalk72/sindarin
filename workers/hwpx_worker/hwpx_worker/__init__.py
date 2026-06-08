"""HWPX worker — native OWPML XML parser (ADR-0003, PRD2 §5.4).

Parses the HWPX zip package: sections, paragraphs, tables, title hierarchy (TOC), document
metadata, and semantic keywords (법령명/기관명/날짜/금액). On package/XML failure, routes to a
render→OCR/VLM ``fallback`` if provided (HWPX-006); the VLM fallback itself goes through the
OpenAI-compatible client per ADR-0003. HWPX is a first-class Korean format (invariant #5).

Requirements: HWPX-001..006 (PRD2 §5.4). Epic E5. Output is validated against the shared IR
gate (``validate_ir``) before return.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from document_ir import DocumentIR, DocumentType, Quality, validate_ir

from hwpx_worker.keywords import extract_keywords
from hwpx_worker.metadata import extract_metadata
from hwpx_worker.package import HwpxPackageError, open_package
from hwpx_worker.parser import parse_outline_levels, parse_sections

__all__ = ["process", "HwpxPackageError"]

_PARSER_VERSION = "0.1.0"


class HwpxFallback(Protocol):
    """Render→OCR/VLM fallback for un-parseable HWPX (HWPX-006)."""

    def __call__(self, source_uri: str, document_id: UUID) -> DocumentIR: ...


def process(
    source_uri: str,
    document_id: UUID,
    *,
    fallback: HwpxFallback | None = None,
) -> DocumentIR:
    try:
        pkg = open_package(source_uri)
    except HwpxPackageError:
        if fallback is None:
            raise
        ir = fallback(source_uri, document_id)
        ir.quality.used_fallback = True
        ir.quality.parse_warnings.append("HWPX native parse failed; used render/OCR fallback")
        return ir

    outline = parse_outline_levels(pkg.header_xml)
    parsed = parse_sections(pkg.section_xmls, outline)
    full_text = "\n".join(b.text for b in parsed.blocks)

    ir = DocumentIR(
        document_id=document_id,
        source_uri=source_uri,
        document_type=DocumentType.HWPX,
        blocks=parsed.blocks,
        semantic_keywords=extract_keywords(full_text),
        metadata=extract_metadata(pkg.content_hpf),
        quality=Quality(
            parser="hwpx-native",
            parser_version=_PARSER_VERSION,
            used_fallback=False,
            parse_warnings=parsed.warnings,
            extraction_coverage=parsed.extraction_coverage,
            table_preservation_score=parsed.table_preservation_score,
        ),
    )

    result = validate_ir(ir)
    if not result.ok:
        raise ValueError(f"hwpx produced invalid IR: {result.errors}")
    return ir
