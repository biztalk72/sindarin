"""IR → retrieval chunks (E6, ADR-0008).

Groups blocks into chunks while preserving the citation anchor: a chunk never spans pages
(``page_no`` stays meaningful) and tables become their own chunk (so table context isn't
split). ``toc_path``/``section_id``/``bbox`` are carried from the lead block. The embedding
worker turns each ``Chunk`` into a ``ChunkPayload`` by adding ACL + embedding fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from document_ir import BBox, Block, BlockType, DocumentIR

DEFAULT_MAX_CHARS = 1200


@dataclass
class Chunk:
    chunk_id: str
    text: str
    document_id: UUID
    page_no: int | None
    section_id: str | None
    toc_path: list[str] = field(default_factory=list)
    bbox: BBox | None = None
    block_refs: list[str] = field(default_factory=list)


def _render_table(block: Block) -> str:
    ts = block.table_schema
    if ts is None:
        return block.text
    lines = [" | ".join(ts.headers)] if ts.headers else []
    lines += [" | ".join(row) for row in ts.rows]
    return "\n".join(lines)


def chunk_document(ir: DocumentIR, *, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[Block] = []
    buf_len = 0

    def new_id() -> str:
        return f"{ir.document_id}_{len(chunks)}"

    def flush() -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        lead = buf[0]
        text = "\n".join(b.text for b in buf if b.text.strip())
        chunks.append(
            Chunk(
                chunk_id=new_id(),
                text=text,
                document_id=ir.document_id,
                page_no=lead.page_no,
                section_id=lead.section_id,
                toc_path=list(lead.section_path),
                bbox=lead.bbox,
                block_refs=[b.block_id for b in buf],
            )
        )
        buf = []
        buf_len = 0

    for block in ir.blocks:
        if block.block_type is BlockType.TABLE:
            flush()
            chunks.append(
                Chunk(
                    chunk_id=new_id(),
                    text=_render_table(block),
                    document_id=ir.document_id,
                    page_no=block.page_no,
                    section_id=block.section_id,
                    toc_path=list(block.section_path),
                    bbox=block.bbox,
                    block_refs=[block.block_id],
                )
            )
            continue

        crosses_page = bool(buf) and block.page_no != buf[0].page_no
        too_big = bool(buf) and buf_len + len(block.text) > max_chars
        if crosses_page or too_big:
            flush()

        buf.append(block)
        buf_len += len(block.text)

    flush()
    return chunks
