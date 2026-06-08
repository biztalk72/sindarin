"""E5 / HWPX-001..006: native HWPX parser. Builds a real OWPML zip in tmp_path."""

import zipfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from document_ir import BlockType, DocumentIR, DocumentType, Quality, validate_ir
from hwpx_worker import HwpxPackageError, process

HEADER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">
  <hh:refList><hh:paraProperties>
    <hh:paraPr id="0"><hh:heading type="NONE" level="0"/></hh:paraPr>
    <hh:paraPr id="1"><hh:heading type="OUTLINE" level="0"/></hh:paraPr>
    <hh:paraPr id="2"><hh:heading type="OUTLINE" level="1"/></hh:paraPr>
  </hh:paraProperties></hh:refList>
</hh:head>"""

SECTION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
        xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p paraPrIDRef="1"><hp:run><hp:t>개인정보 처리방침 개정 공고</hp:t></hp:run></hp:p>
  <hp:p paraPrIDRef="0"><hp:run><hp:t>개인정보 보호법 제30조에 따라 2026-04-15 시행하며 과태료 1,000,000원.</hp:t></hp:run></hp:p>
  <hp:p paraPrIDRef="2"><hp:run><hp:t>세부 내용</hp:t></hp:run></hp:p>
  <hp:tbl>
    <hp:tr>
      <hp:tc><hp:subList><hp:p><hp:run><hp:t>항목</hp:t></hp:run></hp:p></hp:subList></hp:tc>
      <hp:tc><hp:subList><hp:p><hp:run><hp:t>값</hp:t></hp:run></hp:p></hp:subList></hp:tc>
    </hp:tr>
    <hp:tr>
      <hp:tc><hp:subList><hp:p><hp:run><hp:t>보존기간</hp:t></hp:run></hp:p></hp:subList></hp:tc>
      <hp:tc><hp:subList><hp:p><hp:run><hp:t>5년</hp:t></hp:run></hp:p></hp:subList></hp:tc>
    </hp:tr>
  </hp:tbl>
  <hp:p paraPrIDRef="1"><hp:run><hp:t>부칙</hp:t></hp:run></hp:p>
  <hp:p paraPrIDRef="0"><hp:run><hp:t>이 방침은 공포한 날부터 시행한다.</hp:t></hp:run></hp:p>
</hs:sec>"""

CONTENT_HPF = """<?xml version="1.0" encoding="UTF-8"?>
<opf:package xmlns:opf="http://www.idpf.org/2007/opf"
             xmlns:dc="http://purl.org/dc/elements/1.1/">
  <opf:metadata>
    <dc:creator>정보보호팀</dc:creator>
    <dc:date>2026-04-15</dc:date>
    <dc:title>개인정보 처리방침</dc:title>
  </opf:metadata>
</opf:package>"""


@pytest.fixture
def hwpx_file(tmp_path: Path) -> str:
    path = tmp_path / "notice.hwpx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/header.xml", HEADER_XML)
        zf.writestr("Contents/section0.xml", SECTION_XML)
        zf.writestr("Contents/content.hpf", CONTENT_HPF)
    return str(path)


def test_block_types_and_order(hwpx_file: str) -> None:
    ir = process(hwpx_file, uuid4())
    kinds = [b.block_type for b in ir.blocks]
    assert kinds == [
        BlockType.HEADING,
        BlockType.PARAGRAPH,
        BlockType.HEADING,
        BlockType.TABLE,
        BlockType.HEADING,
        BlockType.PARAGRAPH,
    ]


def test_synthetic_pagination_by_outline(hwpx_file: str) -> None:
    ir = process(hwpx_file, uuid4())
    assert ir.blocks[0].page_no == 1  # 공고 (outline L0, shallowest)
    assert ir.blocks[3].page_no == 1  # table under 세부 내용 (L1)
    assert ir.blocks[4].page_no == 2  # 부칙 (L0)
    assert ir.blocks[5].page_no == 2


def test_style_based_toc_nesting(hwpx_file: str) -> None:
    ir = process(hwpx_file, uuid4())
    sub = ir.blocks[2]  # 세부 내용
    assert sub.section_path == ["개인정보 처리방침 개정 공고", "세부 내용"]
    assert ir.blocks[4].section_path == ["부칙"]  # L0 popped previous L0/L1


def test_table_extracted(hwpx_file: str) -> None:
    ir = process(hwpx_file, uuid4())
    table = next(b for b in ir.blocks if b.block_type is BlockType.TABLE)
    assert table.table_schema is not None
    assert table.table_schema.headers == ["항목", "값"]
    assert table.table_schema.rows == [["보존기간", "5년"]]


def test_semantic_keywords(hwpx_file: str) -> None:
    ir = process(hwpx_file, uuid4())
    kinds = {k.kind for k in ir.semantic_keywords}
    kws = {k.keyword for k in ir.semantic_keywords}
    assert {"법령명", "날짜", "금액"} <= kinds
    assert "제30조" in kws
    assert "2026-04-15" in kws


def test_metadata_extracted(hwpx_file: str) -> None:
    ir = process(hwpx_file, uuid4())
    assert ir.metadata.get("author") == "정보보호팀"
    assert ir.metadata.get("created_at") == "2026-04-15"
    assert ir.document_type is DocumentType.HWPX


def test_output_passes_shared_validator(hwpx_file: str) -> None:
    ir = process(hwpx_file, uuid4())
    assert validate_ir(ir).ok


def test_corrupt_package_uses_fallback(tmp_path: Path) -> None:
    bad = tmp_path / "broken.hwpx"
    bad.write_text("not a zip at all")
    doc_id = uuid4()

    def fallback(source_uri: str, document_id: UUID) -> DocumentIR:  # noqa: ARG001
        return DocumentIR(
            document_id=document_id,
            source_uri=source_uri,
            document_type=DocumentType.HWPX,
            blocks=[],
            quality=Quality(parser="vlm-fallback"),
        )

    ir = process(str(bad), doc_id, fallback=fallback)
    assert ir.quality.used_fallback is True
    assert any("fallback" in w for w in ir.quality.parse_warnings)


def test_corrupt_package_without_fallback_raises(tmp_path: Path) -> None:
    bad = tmp_path / "broken.hwpx"
    bad.write_text("not a zip")
    with pytest.raises(HwpxPackageError):
        process(str(bad), uuid4())
