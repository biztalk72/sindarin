"""E4 / OCR-001,005,006: PDF classifier + OCR IR shaping (engine injected/faked)."""

from uuid import uuid4

import pytest
from document_ir import validate_ir
from ocr_worker import OCR_CONFIDENCE_FLOOR, ir_from_digital_pdf, ir_from_ocr, process
from ocr_worker.classifier import classify_from_page_texts, classify_pdf
from ocr_worker.engine import OcrLine, OcrPage

# --- OCR-001 classifier ---


def test_classifier_digital_scanned_hybrid_empty() -> None:
    full = ["a long enough text layer here"] * 5
    assert classify_from_page_texts(full) == "digital"
    assert classify_from_page_texts(["", "", "", "", ""]) == "scanned"
    mixed = ["a long enough text layer here", "", "another decent text block here", "", ""]
    assert classify_from_page_texts(mixed) == "hybrid"
    assert classify_from_page_texts([]) == "scanned"


def test_classify_pdf_uses_injected_extractor() -> None:
    kind = classify_pdf("x.pdf", extractor=lambda _p: ["plenty of digital text here"] * 3)
    assert kind == "digital"


# --- OCR-006 digital path ---


def test_ir_from_digital_pdf_blocks_per_page() -> None:
    ir = ir_from_digital_pdf(uuid4(), "x.pdf", ["page one text", "", "page three text"])
    assert [b.page_no for b in ir.blocks] == [1, 3]  # empty page 2 skipped
    assert validate_ir(ir).ok
    assert ir.quality.parser == "pypdf-text"


# --- OCR-003/006 OCR path + OCR-005 gate ---


def _pages(conf: float) -> list[OcrPage]:
    return [
        OcrPage(
            page_no=1,
            lines=[
                OcrLine(
                    "스캔된 첫 줄", confidence=conf, bbox={"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.05}
                ),
                OcrLine(
                    "스캔된 둘째 줄",
                    confidence=conf,
                    bbox={"x": 0.1, "y": 0.2, "w": 0.8, "h": 0.05},
                ),
            ],
        )
    ]


def test_ir_from_ocr_carries_bbox_and_confidence() -> None:
    ir = ir_from_ocr(uuid4(), "scan.pdf", _pages(0.97))
    assert len(ir.blocks) == 2
    assert ir.blocks[0].bbox is not None
    assert ir.blocks[0].page_no == 1
    assert ir.quality.ocr_confidence == 0.97
    assert ir.quality.parse_warnings == []
    assert validate_ir(ir).ok


def test_ocr_quality_gate_flags_low_confidence() -> None:
    ir = ir_from_ocr(uuid4(), "scan.pdf", _pages(0.40))
    assert ir.quality.ocr_confidence == 0.40
    assert any("needs_reprocess" in w for w in ir.quality.parse_warnings)
    assert OCR_CONFIDENCE_FLOOR == 0.90


# --- routing ---


class FakeEngine:
    def recognize(self, source_uri: str) -> list[OcrPage]:  # noqa: ARG002
        return _pages(0.95)


def test_process_routes_digital_via_text_layer() -> None:
    ir = process("x.pdf", uuid4(), page_texts=["plenty of digital text here"] * 3)
    assert ir.quality.parser == "pypdf-text"


def test_process_routes_scanned_via_engine() -> None:
    ir = process("scan.pdf", uuid4(), page_texts=["", "", ""], ocr_engine=FakeEngine())
    assert ir.quality.parser == "paddleocr-vl"
    assert ir.blocks


def test_process_scanned_without_engine_raises() -> None:
    with pytest.raises(ValueError, match="OcrEngine is required"):
        process("scan.pdf", uuid4(), page_texts=["", "", ""])
