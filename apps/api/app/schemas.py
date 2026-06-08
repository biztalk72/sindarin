"""Chat API contracts (PRD2 §9.1 request, §9.2 response)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChatMode(StrEnum):
    ANSWER = "answer"
    SUMMARY = "summary"
    COMPARE = "compare"
    TABLE_QA = "table_qa"
    RISK_REVIEW = "risk_review"


class ChatScope(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    section_ids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    scope: ChatScope | None = None
    mode: ChatMode = ChatMode.ANSWER
    language: str | None = None  # ko | en | auto
    stream: bool = False
    model_hint: str | None = None


class CitationOut(BaseModel):
    document_id: str
    chunk_id: str
    page_no: int | None = None
    section_path: list[str] = Field(default_factory=list)
    source_span: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    confidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    retrieval_trace_id: str


class DocumentOut(BaseModel):
    """Document card (PRD2 §8.2 UI-DOC-001/002/003)."""

    id: str
    name: str
    type: str
    status: str
    security_level: str
    created_at: str | None = None
    chunk_count: int = 0


class JobOut(BaseModel):
    id: str
    document_id: str
    stage: str
    status: str
