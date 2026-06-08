"""E3 / MD-001..005: MarkItDown worker (injectable converter, no binary needed)."""

from uuid import uuid4

import pytest
from document_ir import BlockType, DocumentType, validate_ir
from markitdown_worker import process

DOCX_MD = """\
# 계약서

본 계약은 목적을 정한다.

## 제1조

- 항목 1
- 항목 2

| 구분 | 금액 |
| --- | --- |
| 해지 | 1000 |
| 위반 | 2000 |

# 부칙

시행일은 즉시.
"""

XLSX_MD = """\
## Sheet1

| a | b |
| --- | --- |
| 1 | 2 |

## Sheet2

| c | d |
| --- | --- |
| 3 | 4 |
"""


class FakeConverter:
    def __init__(self, md: str) -> None:
        self._md = md

    def convert(self, source_path: str) -> str:  # noqa: ARG002
        return self._md


class FailingConverter:
    def convert(self, source_path: str) -> str:  # noqa: ARG002
        raise RuntimeError("libreoffice not available")


def test_docx_block_types_and_order() -> None:
    ir = process("x.docx", uuid4(), converter=FakeConverter(DOCX_MD))
    kinds = [b.block_type for b in ir.blocks]
    assert kinds == [
        BlockType.HEADING,
        BlockType.PARAGRAPH,
        BlockType.HEADING,
        BlockType.LIST,
        BlockType.TABLE,
        BlockType.HEADING,
        BlockType.PARAGRAPH,
    ]


def test_synthetic_pagination_at_shallowest_heading() -> None:
    ir = process("x.docx", uuid4(), converter=FakeConverter(DOCX_MD))
    # Two H1 sections (계약서, 부칙) → pages 1 and 2; the H2 stays on page 1.
    assert ir.blocks[0].page_no == 1  # 계약서
    assert ir.blocks[4].page_no == 1  # table under 제1조
    assert ir.blocks[5].page_no == 2  # 부칙
    assert ir.blocks[6].page_no == 2  # 시행일 paragraph


def test_section_path_nesting() -> None:
    ir = process("x.docx", uuid4(), converter=FakeConverter(DOCX_MD))
    table = next(b for b in ir.blocks if b.block_type is BlockType.TABLE)
    assert table.section_path == ["계약서", "제1조"]
    last = ir.blocks[-1]
    assert last.section_path == ["부칙"]  # H1 popped the previous H1/H2


def test_table_schema_preserved() -> None:
    ir = process("x.docx", uuid4(), converter=FakeConverter(DOCX_MD))
    table = next(b for b in ir.blocks if b.block_type is BlockType.TABLE)
    assert table.table_schema is not None
    assert table.table_schema.headers == ["구분", "금액"]
    assert table.table_schema.rows == [["해지", "1000"], ["위반", "2000"]]


def test_quality_metrics() -> None:
    ir = process("x.docx", uuid4(), converter=FakeConverter(DOCX_MD))
    assert ir.quality.parser == "markitdown"
    assert ir.quality.extraction_coverage == 1.0
    assert ir.quality.table_preservation_score == 1.0
    assert ir.quality.used_fallback is False


def test_output_passes_shared_validator() -> None:
    ir = process("x.docx", uuid4(), converter=FakeConverter(DOCX_MD))
    assert validate_ir(ir).ok


def test_fallback_chain_used_on_primary_failure() -> None:
    ir = process(
        "x.docx",
        uuid4(),
        converter=FailingConverter(),
        fallback=FakeConverter(DOCX_MD),
    )
    assert ir.quality.used_fallback is True
    assert any("fallback" in w for w in ir.quality.parse_warnings)
    assert len(ir.blocks) == 7


def test_no_fallback_reraises() -> None:
    with pytest.raises(RuntimeError):
        process("x.docx", uuid4(), converter=FailingConverter())


def test_xlsx_sheets_paginate_per_sheet() -> None:
    ir = process(
        "x.xlsx", uuid4(), document_type=DocumentType.XLSX, converter=FakeConverter(XLSX_MD)
    )
    headings = [b for b in ir.blocks if b.block_type is BlockType.HEADING]
    tables = [b for b in ir.blocks if b.block_type is BlockType.TABLE]
    assert [h.page_no for h in headings] == [1, 2]  # shallowest level is ## here
    assert [t.page_no for t in tables] == [1, 2]
    assert ir.document_type is DocumentType.XLSX
