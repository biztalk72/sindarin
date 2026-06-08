"""IR-001: cross-parser validator + golden fixtures.

Asserts every parser's golden output validates against the one schema (E2 acceptance) and
that the validator actually rejects the invariant violations it claims to guard.
"""

import json
from pathlib import Path

import pytest
from document_ir import validate_ir

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "ir"
GOLDEN = sorted(FIXTURE_DIR.glob("*.json"))


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", GOLDEN, ids=lambda p: p.stem)
def test_golden_fixtures_validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = validate_ir(data)
    assert result.ok, f"{path.name} failed: {result.errors}"


def test_all_parsers_represented() -> None:
    """MarkItDown, PaddleOCR-VL, and HWPX must each have a golden fixture (E2 acceptance)."""
    parsers = {json.loads(p.read_text(encoding="utf-8"))["quality"]["parser"] for p in GOLDEN}
    assert {"markitdown", "paddleocr-vl", "hwpx-native"} <= parsers


def test_missing_page_no_is_error() -> None:
    data = _load("markitdown_docx.json")
    data["blocks"][0]["page_no"] = None
    result = validate_ir(data)
    assert not result.ok
    assert any("page_no" in e for e in result.errors)


def test_non_one_based_page_no_is_error() -> None:
    data = _load("markitdown_docx.json")
    data["blocks"][0]["page_no"] = 0
    result = validate_ir(data)
    assert not result.ok
    assert any("1-based" in e for e in result.errors)


def test_duplicate_block_id_is_error() -> None:
    data = _load("markitdown_docx.json")
    data["blocks"][1]["block_id"] = data["blocks"][0]["block_id"]
    result = validate_ir(data)
    assert not result.ok
    assert any("duplicate" in e for e in result.errors)


def test_table_without_schema_is_error() -> None:
    data = _load("paddleocr_vl_pdf.json")
    for b in data["blocks"]:
        if b["block_type"] == "table":
            b.pop("table_schema", None)
    result = validate_ir(data)
    assert not result.ok
    assert any("table_schema" in e for e in result.errors)


def test_empty_document_is_error() -> None:
    data = _load("hwpx.json")
    data["blocks"] = []
    result = validate_ir(data)
    assert not result.ok


def test_unknown_parser_warns_not_errors() -> None:
    data = _load("hwpx.json")
    data["quality"]["parser"] = "some-new-engine"
    result = validate_ir(data)
    assert result.ok  # unknown parser must not block
    assert any("unknown parser" in w for w in result.warnings)


def test_low_ocr_confidence_warns() -> None:
    data = _load("paddleocr_vl_pdf.json")
    data["quality"]["ocr_confidence"] = 0.42
    result = validate_ir(data)
    assert result.ok
    assert any("needs_reprocess" in w for w in result.warnings)
