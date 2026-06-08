"""E7: RAG/trust pipeline — retrieval, ACL double-check, citation validation."""

from _ragkit import build_pipeline
from rag_core import (
    AnswerDraft,
    ChunkRecord,
    Claim,
    DeterministicEmbedder,
    detect_language,
    route_model,
    validate_citations,
)


def test_cited_answer_for_matching_query() -> None:
    pipeline, doc_a, _ = build_pipeline("all")  # admin / unrestricted
    res = pipeline.answer("위약금 얼마인가", principals={"admin"})
    assert "위약금" in res.answer
    assert res.citations
    assert res.citations[0].document_id == doc_a
    assert res.citations[0].page_no == 1
    assert res.confidence["groundedness"] > 0
    assert res.language == "ko"


def test_acl_double_check_excludes_unauthorized_document() -> None:
    pipeline, doc_a, doc_b = build_pipeline("a")  # principal may read only doc A
    res = pipeline.answer("급여 지급일", principals={"user"})
    # doc B (급여, confidential) must never surface in citations (Postgres double-check).
    assert all(c.document_id != doc_b for c in res.citations)


def test_acl_empty_scope_returns_grounded_fallback() -> None:
    pipeline, _, _ = build_pipeline("none")  # principal may read nothing
    res = pipeline.answer("위약금", principals={"user"})
    assert "확인할 수 없습니다" in res.answer
    assert res.citations == []
    assert res.confidence["groundedness"] == 0.0
    assert any("authorized" in w for w in res.warnings)


def test_unsupported_claim_is_dropped() -> None:
    # A claim citing a0 but whose text is unrelated must be dropped (ADR-0004).
    draft = AnswerDraft(claims=[Claim(text="화성 탐사 로켓 발사 일정", citations=["a0"])])
    corpus_text = {"a0": "계약 해지 시 위약금은 100만원이다."}
    outcome = validate_citations(draft, corpus_text)
    assert outcome.supported_claims == []
    assert outcome.citation_precision == 0.0


def test_supported_claim_passes_validation() -> None:
    draft = AnswerDraft(claims=[Claim(text="위약금은 100만원이다", citations=["a0"])])
    corpus_text = {"a0": "계약 해지 시 위약금은 100만원이다."}
    outcome = validate_citations(draft, corpus_text)
    assert len(outcome.supported_claims) == 1
    assert outcome.citation_precision == 1.0


def test_confidence_block_shape() -> None:
    pipeline, _, _ = build_pipeline("all")
    res = pipeline.answer("계약 해지", principals={"admin"})
    assert set(res.confidence) == {"groundedness", "citation_coverage", "retrieval_quality"}
    assert res.retrieval_trace_id


def test_language_and_model_routing() -> None:
    assert detect_language("hello world") == "en"
    assert detect_language("계약 해지") == "ko"
    assert route_model("table_qa", None) == "default-answer"
    assert route_model("answer", "gpt-x") == "gpt-x"  # explicit hint wins


def test_chunkrecord_round_trips_through_embedder() -> None:
    rec = ChunkRecord(chunk_id="x", text="계약", document_id=build_pipeline()[1])
    v = DeterministicEmbedder(dim=8).embed([rec.text])[0]
    assert len(v) == 8
