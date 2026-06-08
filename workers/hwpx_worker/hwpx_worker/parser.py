"""HWPX XML → Document IR blocks (HWPX-001/002/003).

Namespace-agnostic: elements are matched by local name (``p``, ``run``, ``t``, ``tbl``,
``tr``, ``tc``, ``paraPr``, ``heading``) so OWPML namespace/version differences don't break
parsing. Outline levels come from header ``paraPr`` styles → headings → TOC nesting +
synthetic 1-based pagination at the shallowest outline level (ADR-0007 anchor approach).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field

from document_ir import Block, BlockType, TableSchema


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter_local(elem: ET.Element, name: str) -> Iterator[ET.Element]:
    for e in elem.iter():
        if _local(e.tag) == name:
            yield e


def _children_local(elem: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in elem if _local(c.tag) == name]


def _text_of(elem: ET.Element) -> str:
    """Concatenate every ``<t>`` descendant's text (runs may hold several)."""
    parts = [e.text or "" for e in _iter_local(elem, "t")]
    return "".join(parts).strip()


def parse_outline_levels(header_xml: str | None) -> dict[str, int]:
    """Map paraPr id → outline level for OUTLINE-type paragraph styles (headings)."""
    if not header_xml:
        return {}
    try:
        root = ET.fromstring(header_xml)
    except ET.ParseError:
        return {}
    levels: dict[str, int] = {}
    for para_pr in _iter_local(root, "paraPr"):
        pid = para_pr.get("id")
        if pid is None:
            continue
        for heading in _iter_local(para_pr, "heading"):
            if (heading.get("type") or "").upper() == "OUTLINE":
                try:
                    levels[pid] = int(heading.get("level", "0"))
                except ValueError:
                    levels[pid] = 0
    return levels


@dataclass
class ParseResult:
    blocks: list[Block]
    warnings: list[str] = field(default_factory=list)
    tables_detected: int = 0
    tables_parsed: int = 0

    @property
    def extraction_coverage(self) -> float:
        if not self.blocks:
            return 0.0
        return round(sum(1 for b in self.blocks if b.text.strip()) / len(self.blocks), 4)

    @property
    def table_preservation_score(self) -> float | None:
        if self.tables_detected == 0:
            return None
        return round(self.tables_parsed / self.tables_detected, 4)


def _parse_table(tbl: ET.Element) -> TableSchema:
    rows: list[list[str]] = []
    for tr in _iter_local(tbl, "tr"):
        cells = [_text_of(tc) for tc in _children_local(tr, "tc")]
        if not cells:  # cells may be deeper than direct children
            cells = [_text_of(tc) for tc in _iter_local(tr, "tc")]
        rows.append(cells)
    headers = rows[0] if rows else []
    body = rows[1:] if len(rows) > 1 else []
    return TableSchema(headers=headers, rows=body, merged_cells=[])


def parse_sections(section_xmls: list[str], outline_levels: dict[str, int]) -> ParseResult:
    result = ParseResult(blocks=[])
    heading_level_values = set(outline_levels.values())
    shallowest = min(heading_level_values) if heading_level_values else None

    section_stack: list[tuple[int, str]] = []  # (outline level, title)
    shallow_count = 0

    def next_id() -> str:
        return f"b{len(result.blocks) + 1}"

    def page() -> int:
        return max(1, shallow_count)

    def sec_id() -> str:
        return f"sec_{max(1, shallow_count)}"

    for sxml in section_xmls:
        try:
            root = ET.fromstring(sxml)
        except ET.ParseError as exc:
            result.warnings.append(f"section parse error: {exc}")
            continue

        # Top-level body elements in document order: paragraphs and tables.
        for child in root:
            name = _local(child.tag)

            if name == "p":
                para_ref = child.get("paraPrIDRef")
                level = outline_levels.get(para_ref) if para_ref is not None else None
                text = _text_of(child)

                if level is not None:  # heading
                    if shallowest is not None and level == shallowest:
                        shallow_count += 1
                    while section_stack and section_stack[-1][0] >= level:
                        section_stack.pop()
                    section_stack.append((level, text))
                    result.blocks.append(
                        Block(
                            block_id=next_id(),
                            block_type=BlockType.HEADING,
                            text=text,
                            page_no=page(),
                            section_id=sec_id(),
                            section_path=[t for _, t in section_stack],
                        )
                    )
                elif text:
                    result.blocks.append(
                        Block(
                            block_id=next_id(),
                            block_type=BlockType.PARAGRAPH,
                            text=text,
                            page_no=page(),
                            section_id=sec_id(),
                            section_path=[t for _, t in section_stack],
                        )
                    )

            elif name == "tbl":
                result.tables_detected += 1
                schema = _parse_table(child)
                if schema.rows or schema.headers:
                    result.tables_parsed += 1
                else:
                    result.warnings.append("table has no parseable cells")
                result.blocks.append(
                    Block(
                        block_id=next_id(),
                        block_type=BlockType.TABLE,
                        text=" | ".join(schema.headers),
                        page_no=page(),
                        section_id=sec_id(),
                        section_path=[t for _, t in section_stack],
                        table_schema=schema,
                    )
                )

    if not result.blocks:
        result.warnings.append("no blocks extracted from HWPX sections")
    return result
