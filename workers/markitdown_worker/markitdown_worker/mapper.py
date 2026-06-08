"""Markdown → Document IR blocks (MD-002, MD-003, MD-004, ADR-0007).

Maps a flat Markdown string onto canonical ``Block``s and **synthetically paginates at the
shallowest heading level present** so every block keeps a 1-based ``page_no`` (the citation
anchor). This is a deliberately small Markdown reader (headings, GFM tables, lists,
paragraphs) — enough for MarkItDown output, not a full CommonMark parser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from document_ir import Block, BlockType, TableSchema

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")
_LIST_ITEM = re.compile(r"^\s*([-*+]|\d+\.)\s+\S")


@dataclass
class MapResult:
    blocks: list[Block]
    warnings: list[str] = field(default_factory=list)
    tables_detected: int = 0
    tables_parsed: int = 0

    @property
    def extraction_coverage(self) -> float:
        if not self.blocks:
            return 0.0
        non_empty = sum(1 for b in self.blocks if b.text.strip())
        return round(non_empty / len(self.blocks), 4)

    @property
    def table_preservation_score(self) -> float | None:
        if self.tables_detected == 0:
            return None
        return round(self.tables_parsed / self.tables_detected, 4)


def _split_row(line: str) -> list[str]:
    cells = line.strip().split("|")
    # Drop the empty strings produced by leading/trailing pipes.
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def markdown_to_blocks(md: str) -> MapResult:
    lines = md.splitlines()

    heading_levels = [len(m.group(1)) for line in lines if (m := _HEADING.match(line))]
    shallowest = min(heading_levels) if heading_levels else None

    result = MapResult(blocks=[])
    section_stack: list[tuple[int, str]] = []  # (level, title)
    shallow_count = 0
    n = 0

    def next_id() -> str:
        return f"b{len(result.blocks) + 1}"

    def page() -> int:
        return max(1, shallow_count)

    def section_id() -> str:
        return f"sec_{max(1, shallow_count)}"

    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        m = _HEADING.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            if shallowest is not None and level == shallowest:
                shallow_count += 1
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()
            section_stack.append((level, title))
            result.blocks.append(
                Block(
                    block_id=next_id(),
                    block_type=BlockType.HEADING,
                    text=title,
                    page_no=page(),
                    section_id=section_id(),
                    section_path=[t for _, t in section_stack],
                    markdown=line.strip(),
                )
            )
            i += 1
            continue

        # GFM table: a pipe row followed by a separator row.
        if _TABLE_ROW.match(line) and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            result.tables_detected += 1
            headers = _split_row(line)
            rows: list[list[str]] = []
            j = i + 2
            while j < len(lines) and _TABLE_ROW.match(lines[j]):
                rows.append(_split_row(lines[j]))
                j += 1
            if rows:
                result.tables_parsed += 1
            else:
                result.warnings.append(f"table at line {i + 1} has no body rows")
            result.blocks.append(
                Block(
                    block_id=next_id(),
                    block_type=BlockType.TABLE,
                    text=" | ".join(headers),
                    page_no=page(),
                    section_id=section_id(),
                    section_path=[t for _, t in section_stack],
                    table_schema=TableSchema(headers=headers, rows=rows, merged_cells=[]),
                )
            )
            i = j
            continue

        # List: consecutive list items → one LIST block.
        if _LIST_ITEM.match(line):
            items = []
            while i < len(lines) and _LIST_ITEM.match(lines[i]):
                items.append(lines[i].strip())
                i += 1
            result.blocks.append(
                Block(
                    block_id=next_id(),
                    block_type=BlockType.LIST,
                    text="\n".join(items),
                    page_no=page(),
                    section_id=section_id(),
                    section_path=[t for _, t in section_stack],
                    markdown="\n".join(items),
                )
            )
            continue

        # Paragraph: consecutive plain lines until blank / heading / table / list.
        para = []
        while i < len(lines) and lines[i].strip():
            nxt = lines[i]
            if _HEADING.match(nxt) or _LIST_ITEM.match(nxt):
                break
            if _TABLE_ROW.match(nxt) and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
                break
            para.append(nxt.strip())
            i += 1
        text = " ".join(para).strip()
        if text:
            result.blocks.append(
                Block(
                    block_id=next_id(),
                    block_type=BlockType.PARAGRAPH,
                    text=text,
                    page_no=page(),
                    section_id=section_id(),
                    section_path=[t for _, t in section_stack],
                )
            )
        n += 1
        if n > len(lines) + 10:  # defensive: never spin
            break

    if not result.blocks:
        result.warnings.append("no blocks extracted from markdown")
    return result
