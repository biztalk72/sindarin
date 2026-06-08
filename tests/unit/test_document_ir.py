"""Document IR + vector payload contract (PRD2 §6.1, §6.3).

Asserts the citation anchor (document_id, page_no, bbox) is constructible and survives from
IR into the chunk payload — the invariant #3 / ADR-0004 guarantee, in miniature.
"""

from uuid import uuid4

from document_ir import BBox, Block, BlockType, DocumentIR, DocumentType, Quality
from hybrid_idp_shared import SecurityLevel
from rag_core import ChunkPayload


def test_document_ir_minimal() -> None:
    doc_id = uuid4()
    ir = DocumentIR(
        document_id=doc_id,
        source_uri="s3://hybrid-idp/sample.pdf",
        document_type=DocumentType.PDF,
        blocks=[
            Block(
                block_id="blk_1",
                block_type=BlockType.PARAGRAPH,
                text="계약 해지 시 위약금이 발생한다.",
                page_no=12,
                bbox=BBox(x=0.1, y=0.2, w=0.5, h=0.05),
            )
        ],
        quality=Quality(parser="paddleocr-vl", ocr_confidence=0.93),
    )
    assert ir.blocks[0].page_no == 12
    assert ir.quality.parser == "paddleocr-vl"


def test_chunk_payload_carries_citation_anchor() -> None:
    doc_id, ver_id = uuid4(), uuid4()
    payload = ChunkPayload(
        chunk_id="chk_01",
        document_id=doc_id,
        document_version_id=ver_id,
        page_no=12,
        bbox=BBox(x=0.1, y=0.2, w=0.5, h=0.05),
        toc_path=["계약", "해지", "위약금"],
        security_level=SecurityLevel.CONFIDENTIAL,
        acl_hash="deadbeef",
        parser="paddleocr-vl",
        embedding_model="placeholder",
        embedding_version="v1",
    )
    # Anchor preserved into the retrieval layer.
    assert payload.page_no == 12
    assert payload.document_id == doc_id
    assert payload.toc_path[-1] == "위약금"
