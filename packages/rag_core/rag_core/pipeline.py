"""RAG orchestration (E7, PRD2 §7, §9.2).

Wires the trust pipeline end-to-end: query understanding → scope/ACL → hybrid retrieve →
context packing → generate → citation validation → response. All external pieces (embedder,
store, bm25, authorizer, generator) are injected, so the same orchestration runs with the
deterministic dev stack or real models. Uncited/unsupported claims are dropped (ADR-0004);
if nothing survives, the answer is the honest "근거를 찾을 수 없음" fallback (PRD2 §7.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID, uuid4

from rag_core.embedder import Embedder
from rag_core.generator import Generator
from rag_core.guardrails import detect_injection, detect_pii, redact_pii, strip_injection
from rag_core.keyword_index import BM25Index
from rag_core.retrieval import Authorizer, Candidate, ChunkRecord, acl_filter, hybrid_retrieve
from rag_core.trust import validate_citations
from rag_core.vectorstore import VectorStore

_HANGUL = re.compile(r"[가-힣]")

# Rule-based model router v1 (ADR-0001 OpenAI-compat; LLM-judged routing deferred, PRD2 §15).
_MODEL_BY_MODE = {
    "answer": "default-answer",
    "summary": "default-answer",
    "compare": "default-answer",
    "table_qa": "default-answer",
    "risk_review": "default-answer",
}


def detect_language(text: str) -> str:
    return "ko" if _HANGUL.search(text) else "en"


def route_model(mode: str, model_hint: str | None) -> str:
    return model_hint or _MODEL_BY_MODE.get(mode, "default-answer")


@dataclass
class Citation:
    document_id: UUID
    chunk_id: str
    page_no: int | None
    section_path: list[str]
    source_span: str


@dataclass
class ChatResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    retrieval_trace_id: str = ""
    language: str = "en"
    model: str = ""
    guardrails: dict[str, Any] = field(default_factory=dict)  # ADR-0006 audit signal


def pack_context(candidates: list[Candidate], *, budget_chars: int = 6000) -> list[Candidate]:
    """Dedup by chunk and cap by budget, **preserving relevance order**.

    Relevance order is kept so the budget retains the most relevant chunks and downstream
    claim selection is deterministic. Per-document/page reading-order assembly (for the LLM
    prompt string) is a presentation concern handled at prompt-build time, not here.
    """
    seen: set[str] = set()
    packed: list[Candidate] = []
    used = 0
    for c in candidates:
        if c.record.chunk_id in seen:
            continue
        seen.add(c.record.chunk_id)
        used += len(c.record.text)
        packed.append(c)
        if used >= budget_chars:
            break
    return packed


@dataclass
class RagPipeline:
    embedder: Embedder
    store: VectorStore
    bm25: BM25Index
    corpus: dict[str, ChunkRecord]
    authorizer: Authorizer
    generator: Generator
    collection: str = "documents"

    def answer(
        self,
        message: str,
        *,
        principals: set[str],
        mode: str = "answer",
        model_hint: str | None = None,
        scope_document_ids: set[UUID] | None = None,
        payload_filter: dict[str, list[Any]] | None = None,
        top_k: int = 10,
    ) -> ChatResult:
        trace_id = uuid4().hex
        language = detect_language(message)
        model = route_model(mode, model_hint)

        candidates = hybrid_retrieve(
            message,
            embedder=self.embedder,
            store=self.store,
            collection=self.collection,
            bm25=self.bm25,
            corpus=self.corpus,
            top_k=top_k,
            payload_filter=payload_filter,
        )
        candidates = acl_filter(candidates, principals, self.authorizer)
        if scope_document_ids is not None:  # user-selected document scope
            candidates = [c for c in candidates if c.record.document_id in scope_document_ids]

        warnings: list[str] = []
        if not candidates:
            return ChatResult(
                answer="제공된 문서에서 확인할 수 없습니다.",
                confidence={
                    "groundedness": 0.0,
                    "citation_coverage": 0.0,
                    "retrieval_quality": 0.0,
                },
                warnings=["no authorized documents matched the query"],
                retrieval_trace_id=trace_id,
                language=language,
                model=model,
            )

        packed = pack_context(candidates, budget_chars=6000)

        # Guardrails — input scan + strip injected instructions from document context before
        # it reaches the model (ADR-0006, PRD2 §7.1). Citations still use the original corpus.
        input_pii = detect_pii(message)
        injection_hits: list[str] = []
        clean_packed: list[Candidate] = []
        for c in packed:
            cleaned, removed = strip_injection(c.record.text)
            injection_hits.extend(detect_injection(c.record.text))
            injection_hits.extend(removed)
            if removed:
                clean_packed.append(replace(c, record=replace(c.record, text=cleaned)))
            else:
                clean_packed.append(c)
        if input_pii:
            warnings.append(f"input PII detected ({len(input_pii)})")
        if injection_hits:
            warnings.append(f"prompt injection stripped from context ({len(injection_hits)})")

        draft = self.generator.generate(message, clean_packed)
        if draft.model_outcome == "json_retry":
            warnings.append("model returned non-JSON; recovered on retry")
        elif draft.model_outcome == "json_failed":
            warnings.append("model returned non-JSON; no answer produced")
        corpus_text = {cid: rec.text for cid, rec in self.corpus.items()}
        trust = validate_citations(draft, corpus_text)

        guardrails = {
            "input_pii": len(input_pii),
            "injection_removed": len(injection_hits),
            "output_pii": 0,
        }

        supported = trust.supported_claims
        if not supported:
            warnings.append("no claim survived citation validation")
            return ChatResult(
                answer="제공된 문서에서 확인할 수 없습니다.",
                confidence={
                    "groundedness": 0.0,
                    "citation_coverage": trust.citation_coverage,
                    "retrieval_quality": round(packed[0].score, 4) if packed else 0.0,
                },
                warnings=warnings,
                retrieval_trace_id=trace_id,
                language=language,
                model=model,
                guardrails=guardrails,
            )

        citations: list[Citation] = []
        for claim in supported:
            for cid in claim.citations:
                rec = self.corpus.get(cid)
                if rec is None:
                    continue
                span, span_pii = redact_pii(rec.text[:240])
                guardrails["output_pii"] += len(span_pii)
                citations.append(
                    Citation(
                        document_id=rec.document_id,
                        chunk_id=cid,
                        page_no=rec.page_no,
                        section_path=rec.toc_path,
                        source_span=span,
                    )
                )

        # Output PII filter — redact before returning (ADR-0006).
        answer, answer_pii = redact_pii(" ".join(c.text for c in supported))
        guardrails["output_pii"] += len(answer_pii)
        if guardrails["output_pii"]:
            warnings.append(f"output PII redacted ({guardrails['output_pii']})")

        return ChatResult(
            answer=answer,
            citations=citations,
            confidence={
                "groundedness": trust.citation_precision,
                "citation_coverage": trust.citation_coverage,
                "retrieval_quality": round(packed[0].score, 4),
            },
            warnings=warnings,
            retrieval_trace_id=trace_id,
            language=language,
            model=model,
            guardrails=guardrails,
        )
