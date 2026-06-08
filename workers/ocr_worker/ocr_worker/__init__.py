"""OCR worker — PaddleOCR + PaddleOCR-VL (ADR-0009, PRD2 §5.3).

Routes by PDF classification (OCR-001): digital-native PDFs use the text layer directly;
scanned/hybrid go through the injectable OCR engine (render + OCR/VL, env-blocked real impl).
Both paths emit Document IR carrying the citation anchor — page_no + bbox + block_id
(OCR-006) — and apply the confidence quality gate (OCR-005). Output is validated against the
shared IR gate.

Requirements: OCR-001..006 (PRD2 §5.3). Epic E4.
"""

from __future__ import annotations

from uuid import UUID

from document_ir import BBox, Block, BlockType, DocumentIR, DocumentType, Quality, validate_ir

from ocr_worker.classifier import PdfKind, classify_from_page_texts
from ocr_worker.engine import OcrEngine, OcrPage

__all__ = ["process", "ir_from_digital_pdf", "ir_from_ocr", "OCR_CONFIDENCE_FLOOR"]

OCR_CONFIDENCE_FLOOR = 0.90  # OCR-005
_PARSER_VERSION = "0.1.0"


def _coverage(blocks: list[Block]) -> float:
    if not blocks:
        return 0.0
    return round(sum(1 for b in blocks if b.text.strip()) / len(blocks), 4)


def ir_from_digital_pdf(document_id: UUID, source_uri: str, page_texts: list[str]) -> DocumentIR:
    """Born-digital path: one paragraph block per page from the text layer."""
    blocks = [
        Block(block_id=f"p{i}", block_type=BlockType.PARAGRAPH, text=text.strip(), page_no=i)
        for i, text in enumerate(page_texts, start=1)
        if text.strip()
    ]
    ir = DocumentIR(
        document_id=document_id,
        source_uri=source_uri,
        document_type=DocumentType.PDF,
        blocks=blocks,
        quality=Quality(
            parser="pypdf-text",
            parser_version=_PARSER_VERSION,
            extraction_coverage=_coverage(blocks),
        ),
    )
    _ensure_valid(ir)
    return ir


def ir_from_ocr(document_id: UUID, source_uri: str, pages: list[OcrPage]) -> DocumentIR:
    """Scanned/hybrid path: OCR lines → blocks with bbox + confidence (OCR-003/006)."""
    blocks: list[Block] = []
    confidences: list[float] = []
    for page in pages:
        for j, line in enumerate(page.lines):
            if not line.text.strip():
                continue
            confidences.append(line.confidence)
            blocks.append(
                Block(
                    block_id=f"p{page.page_no}_l{j}",
                    block_type=BlockType.PARAGRAPH,
                    text=line.text.strip(),
                    page_no=page.page_no,
                    bbox=BBox(**line.bbox) if line.bbox else None,
                )
            )

    mean_conf = round(sum(confidences) / len(confidences), 4) if confidences else None
    warnings: list[str] = []
    if mean_conf is not None and mean_conf < OCR_CONFIDENCE_FLOOR:
        warnings.append(
            f"mean OCR confidence {mean_conf} < {OCR_CONFIDENCE_FLOOR} → needs_reprocess (OCR-005)"
        )

    ir = DocumentIR(
        document_id=document_id,
        source_uri=source_uri,
        document_type=DocumentType.PDF,
        blocks=blocks,
        quality=Quality(
            parser="paddleocr-vl",
            parser_version=_PARSER_VERSION,
            ocr_confidence=mean_conf,
            parse_warnings=warnings,
            extraction_coverage=_coverage(blocks),
        ),
    )
    _ensure_valid(ir)
    return ir


def process(
    source_uri: str,
    document_id: UUID,
    *,
    page_texts: list[str] | None = None,
    ocr_engine: OcrEngine | None = None,
) -> DocumentIR:
    """Classify then route. ``page_texts`` (if provided) supplies the digital-path text layer.

    digital → text layer; scanned/hybrid → ``ocr_engine.recognize`` (required for those kinds).
    """
    kind: PdfKind = classify_from_page_texts(page_texts or [])
    if kind == "digital" and page_texts:
        return ir_from_digital_pdf(document_id, source_uri, page_texts)

    if ocr_engine is None:
        raise ValueError(f"PDF classified as {kind!r}; an OcrEngine is required to process it")
    return ir_from_ocr(document_id, source_uri, ocr_engine.recognize(source_uri))


def _ensure_valid(ir: DocumentIR) -> None:
    result = validate_ir(ir)
    if not result.ok:
        raise ValueError(f"ocr produced invalid IR: {result.errors}")
