"""Citation validation + groundedness (E7, ADR-0004, PRD2 §7.1).

"Proof beats fluency": each claim must cite a source span that actually supports it. Claims
whose cited chunk doesn't support them (lexical-overlap proxy here; an LLM-judge is the real
entailment check, env-blocked) are **dropped** before the answer is returned. Produces the
confidence signals for PRD2 §9.2 (citation coverage, groundedness).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_core.keyword_index import tokenize

SUPPORT_THRESHOLD = 0.5  # fraction of claim tokens that must appear in the cited span


@dataclass
class Claim:
    text: str
    citations: list[str]  # chunk_ids


@dataclass
class AnswerDraft:
    claims: list[Claim] = field(default_factory=list)
    # Generator-side outcome surfaced to the pipeline so it can warn the user. "ok" is the
    # happy path; "json_retry" = parsed only after a temp-bump retry; "json_failed" = even
    # the retry returned unparseable content (claims will be empty).
    model_outcome: str = "ok"


@dataclass
class ValidatedClaim:
    text: str
    citations: list[str]
    supported: bool


@dataclass
class TrustOutcome:
    claims: list[ValidatedClaim]
    citation_precision: float
    citation_coverage: float

    @property
    def supported_claims(self) -> list[ValidatedClaim]:
        return [c for c in self.claims if c.supported]


def _supports(claim_text: str, source_text: str) -> bool:
    claim_tokens = set(tokenize(claim_text))
    if not claim_tokens:
        return False
    source_tokens = set(tokenize(source_text))
    overlap = len(claim_tokens & source_tokens) / len(claim_tokens)
    return overlap >= SUPPORT_THRESHOLD


def validate_citations(draft: AnswerDraft, corpus_text: dict[str, str]) -> TrustOutcome:
    """Validate each claim against its cited source; drop unsupported/uncited (ADR-0004)."""
    validated: list[ValidatedClaim] = []
    for claim in draft.claims:
        cited_texts = [corpus_text[c] for c in claim.citations if c in corpus_text]
        supported = bool(cited_texts) and any(_supports(claim.text, t) for t in cited_texts)
        validated.append(
            ValidatedClaim(text=claim.text, citations=claim.citations, supported=supported)
        )

    total = len(validated)
    n_supported = sum(1 for c in validated if c.supported)
    precision = round(n_supported / total, 4) if total else 0.0
    coverage = precision  # supported-claim fraction is our coverage proxy
    return TrustOutcome(claims=validated, citation_precision=precision, citation_coverage=coverage)
