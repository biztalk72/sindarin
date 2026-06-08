"""Eval worker — citation/groundedness/retrieval metrics (E8, PRD2 §7, §10.2).

Runs a golden query set through the RAG pipeline and aggregates the release-gate metrics
(`tests/eval/thresholds.toml`): Recall@10, citation-anchor accuracy, citation precision, and
unsupported-claim rate. The pipeline is duck-typed (anything with ``.answer(...) -> ChatResult``)
so this stays decoupled from the app wiring. LLM-judge faithfulness is a follow-up.

Requirements: TRUST-001 (PRD2 §7.1). Epic E8.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class _Pipeline(Protocol):
    def answer(self, message: str, *, principals: set[str], top_k: int = 10) -> Any: ...


@dataclass
class QueryEval:
    query: str
    expected_document_id: UUID
    cited_document_ids: list[UUID]
    groundedness: float

    @property
    def hit(self) -> bool:
        return self.expected_document_id in self.cited_document_ids

    @property
    def anchor_correct(self) -> bool:
        # Doc-level anchor: the answer cites the correct source document. Page-level anchor
        # accuracy needs page-labelled golden data + a reliable reranker (follow-up).
        return self.hit


def run_query_evals(
    pipeline: _Pipeline,
    golden: list[tuple[str, UUID]],
    *,
    principals: set[str] | None = None,
    top_k: int = 10,
) -> list[QueryEval]:
    principals = principals or {"admin"}
    evals: list[QueryEval] = []
    for query, expected in golden:
        res = pipeline.answer(query, principals=principals, top_k=top_k)
        evals.append(
            QueryEval(
                query=query,
                expected_document_id=expected,
                cited_document_ids=[c.document_id for c in res.citations],
                groundedness=float(res.confidence.get("groundedness", 0.0)),
            )
        )
    return evals


def aggregate(evals: list[QueryEval]) -> dict[str, float]:
    n = len(evals) or 1
    return {
        "recall_at_10": round(sum(e.hit for e in evals) / n, 4),
        "citation_anchor_accuracy": round(sum(e.anchor_correct for e in evals) / n, 4),
        "citation_precision": round(sum(e.groundedness for e in evals) / n, 4),
        "unsupported_claim_rate": round(sum(1 for e in evals if e.groundedness < 1.0) / n, 4),
    }


def evaluate(pipeline: _Pipeline, golden: list[tuple[str, UUID]], **kw: Any) -> dict[str, float]:
    return aggregate(run_query_evals(pipeline, golden, **kw))
