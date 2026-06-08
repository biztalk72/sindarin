"""Cross-parser IR validator (IR-001).

Every preprocessing worker (MarkItDown, PaddleOCR/-VL, HWPX) must produce output that
passes ``validate_ir``. This is the shared gate that makes "all parsers emit the same
schema" enforceable (PRD2 §6.1, acceptance for epic E2).

Two tiers:
- **schema** — pydantic structural validation of ``DocumentIR``.
- **invariants** — semantic rules pydantic can't express, grounded in the ADRs:
  the citation anchor must survive (``page_no`` present + 1-based, ADR-0004/ADR-0007),
  block ids are unique, table blocks carry a ``table_schema`` (MD-003/HWPX-003), etc.

Errors fail validation; warnings are advisory (e.g. low OCR confidence → reprocess candidate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from document_ir.models import BlockType, DocumentIR

# Parsers we recognize (PRD2 §6.3 ``parser`` examples). Unknown → warning, not error,
# so new engines aren't blocked before their ADR lands.
KNOWN_PARSERS = frozenset(
    {
        "markitdown",
        "paddleocr",
        "paddleocr-vl",
        "hwpx-native",
        "hwp5-fallback",
        "vlm-fallback",
    }
)

# OCR confidence gate (PRD2 §10.2 / OCR-005): below this, flag for reprocessing.
OCR_CONFIDENCE_FLOOR = 0.90


@dataclass
class IRValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def validate_ir(data: DocumentIR | dict[str, Any]) -> IRValidationResult:
    """Validate parser output against the schema + IR invariants."""
    # Tier 1: schema.
    if isinstance(data, DocumentIR):
        ir = data
    else:
        try:
            ir = DocumentIR.model_validate(data)
        except ValidationError as exc:
            return IRValidationResult(ok=False, errors=[f"schema: {e}" for e in _flatten(exc)])

    errors: list[str] = []
    warnings: list[str] = []

    # Tier 2: invariants.
    if not ir.blocks:
        errors.append("document has no blocks (a parsed document must yield ≥1 block)")

    if ir.quality.parser not in KNOWN_PARSERS:
        warnings.append(f"unknown parser {ir.quality.parser!r} (not in KNOWN_PARSERS)")

    if ir.quality.ocr_confidence is not None and ir.quality.ocr_confidence < OCR_CONFIDENCE_FLOOR:
        warnings.append(
            f"ocr_confidence {ir.quality.ocr_confidence:.2f} < {OCR_CONFIDENCE_FLOOR} "
            "→ needs_reprocess candidate (OCR-005)"
        )

    seen: set[str] = set()
    for i, block in enumerate(ir.blocks):
        loc = f"block[{i}] id={block.block_id!r}"

        if not block.block_id:
            errors.append(f"{loc}: empty block_id")
        elif block.block_id in seen:
            errors.append(f"{loc}: duplicate block_id")
        else:
            seen.add(block.block_id)

        # Citation anchor must survive into every block (invariant #3 / ADR-0004, ADR-0007).
        if block.page_no is None:
            errors.append(f"{loc}: missing page_no (citation anchor required)")
        elif block.page_no < 1:
            errors.append(f"{loc}: page_no {block.page_no} is not 1-based")

        if block.block_type is BlockType.TABLE and block.table_schema is None:
            errors.append(f"{loc}: TABLE block without table_schema (MD-003/HWPX-003)")

        if block.bbox is not None and (block.bbox.w <= 0 or block.bbox.h <= 0):
            warnings.append(f"{loc}: bbox has non-positive area")

        if block.block_type in (BlockType.PARAGRAPH, BlockType.HEADING) and not block.text.strip():
            warnings.append(f"{loc}: empty text for {block.block_type} block")

    return IRValidationResult(ok=not errors, errors=errors, warnings=warnings)


def _flatten(exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        out.append(f"{loc}: {err['msg']}")
    return out
