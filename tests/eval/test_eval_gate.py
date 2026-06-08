"""E8 release-gate eval (PRD2 §10.2). Runs a golden query set through the deterministic
pipeline and asserts the metrics meet the floors in thresholds.toml. Marked `eval`.

Offline-capable (deterministic embedder + extractive generator) so the gate runs in CI
without an LLM endpoint; with a real model it measures the same metrics on the same path.
"""

import tomllib
from pathlib import Path
from uuid import uuid4

import pytest
from eval_worker import evaluate
from rag_core import (
    BM25Index,
    ChunkRecord,
    DeterministicEmbedder,
    DeterministicGenerator,
    InMemoryVectorStore,
    RagPipeline,
)

pytestmark = pytest.mark.eval

THRESHOLDS = tomllib.loads((Path(__file__).parent / "thresholds.toml").read_text())


class _AdminAuthorizer:
    def allowed_documents(self, principals):  # noqa: ARG002
        return None


def _build():
    docs = {
        "위약금": "계약 해지 시 위약금은 100만원으로 한다.",
        "급여": "급여는 매월 25일에 지급된다.",
        "휴가": "연차 휴가는 매년 15일 부여된다.",
    }
    ids = {topic: uuid4() for topic in docs}
    corpus = {
        topic: ChunkRecord(chunk_id=topic, text=text, document_id=ids[topic], page_no=1)
        for topic, text in docs.items()
    }
    embedder = DeterministicEmbedder(dim=64)
    store = InMemoryVectorStore()
    store.ensure_collection("documents", 64)
    store.upsert(
        "documents",
        [(t, embedder.embed([r.text])[0], {"document_id": str(r.document_id)}) for t, r in corpus.items()],
    )
    bm25 = BM25Index()
    bm25.index([(t, r.text) for t, r in corpus.items()])
    pipeline = RagPipeline(
        embedder=embedder, store=store, bm25=bm25, corpus=corpus,
        authorizer=_AdminAuthorizer(), generator=DeterministicGenerator(), collection="documents",
    )
    golden = [
        ("위약금 얼마인가", ids["위약금"]),
        ("급여 지급일", ids["급여"]),
        ("연차 휴가 일수", ids["휴가"]),
    ]
    return pipeline, golden


def test_eval_gate_meets_thresholds() -> None:
    pipeline, golden = _build()
    metrics = evaluate(pipeline, golden)

    assert metrics["recall_at_10"] >= THRESHOLDS["retrieval"]["recall_at_10"], metrics
    assert (
        metrics["citation_anchor_accuracy"] >= THRESHOLDS["retrieval"]["citation_anchor_accuracy"]
    ), metrics
    assert metrics["citation_precision"] >= THRESHOLDS["trust"]["citation_precision"], metrics
    assert (
        metrics["unsupported_claim_rate"] <= THRESHOLDS["trust"]["unsupported_claim_rate_max"]
    ), metrics
