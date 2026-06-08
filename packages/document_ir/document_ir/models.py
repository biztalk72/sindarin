"""Document IR pydantic models — mirrors PRD2 §6.1 field table.

Keep this module the authoritative schema. Parser tests assert their output validates here;
the vector payload contract (PRD2 §6.3, see ``rag_core``) is derived from these fields.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    HWPX = "hwpx"
    HWP = "hwp"
    IMAGE = "image"
    HTML = "html"
    CSV = "csv"
    JSON = "json"
    XML = "xml"


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    CELL = "cell"
    SLIDE = "slide"
    SHEET = "sheet"


class BBox(BaseModel):
    """Coordinate box for PDF/image-derived blocks (PRD2 §6.1 ``bbox``)."""

    x: float
    y: float
    w: float
    h: float


class TableSchema(BaseModel):
    """Structured table preservation (PRD2 §6.1 ``table_schema`` / §5.2 MD-003)."""

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    merged_cells: list[dict[str, Any]] = Field(default_factory=list)
    caption: str | None = None


class SemanticKeyword(BaseModel):
    """Business keyword / entity (PRD2 §6.1 ``semantic_keywords`` / §5.4 HWPX-005)."""

    keyword: str
    kind: str | None = None  # e.g. 법령명, 기관명, 제품명, 날짜, 금액, 약어
    weight: float | None = None
    confidence: float | None = None


class Quality(BaseModel):
    """Parser quality signals (PRD2 §6.1 ``quality`` / §5.2 MD-004)."""

    ocr_confidence: float | None = None
    parse_warnings: list[str] = Field(default_factory=list)
    used_fallback: bool = False
    parser: str  # markitdown | paddleocr | paddleocr-vl | hwpx-native | ...
    parser_version: str | None = None
    extraction_coverage: float | None = None  # fraction of blocks with non-empty text
    table_preservation_score: float | None = None  # parsed/detected tables, or None if no tables


class Block(BaseModel):
    """A search/citation unit: paragraph, table, figure, cell, slide, sheet.

    ``page_no`` is the citation anchor; for flow formats it may be a synthetic
    section/sheet ordinal (ADR-0007) but is always present and 1-based.
    """

    block_id: str
    block_type: BlockType
    text: str
    page_no: int | None = None
    section_id: str | None = None
    section_path: list[str] = Field(default_factory=list)
    markdown: str | None = None
    bbox: BBox | None = None
    table_schema: TableSchema | None = None


class DocumentIR(BaseModel):
    """Normalized representation of one document version (PRD2 §6.1)."""

    document_id: UUID
    source_uri: str
    document_type: DocumentType
    blocks: list[Block] = Field(default_factory=list)
    semantic_keywords: list[SemanticKeyword] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)  # author/dates/dept/acl tags
    quality: Quality
