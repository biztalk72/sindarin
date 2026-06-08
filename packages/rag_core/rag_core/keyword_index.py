"""BM25 keyword index (E6, PRD2 §7 keyword retrieval).

Complements vector search for exact-term / document-number / 법령명 queries where embeddings
under-recall. Pure-Python Okapi BM25 over chunk texts — no external service. Tokenizer keeps
ASCII alphanumerics and Hangul runs.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

_TOKEN = re.compile(r"[0-9a-zA-Z]+|[가-힣]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class BM25Index:
    k1: float = 1.5
    b: float = 0.75
    _docs: list[str] = field(default_factory=list)
    _tokens: list[list[str]] = field(default_factory=list)
    _df: Counter[str] = field(default_factory=Counter)
    _avg_len: float = 0.0

    def index(self, docs: list[tuple[str, str]]) -> None:
        """docs: list of (chunk_id, text)."""
        self._docs = [cid for cid, _ in docs]
        self._tokens = [tokenize(text) for _, text in docs]
        self._df = Counter()
        for toks in self._tokens:
            for term in set(toks):
                self._df[term] += 1
        self._avg_len = (
            (sum(len(t) for t in self._tokens) / len(self._tokens)) if self._tokens else 0.0
        )

    def _idf(self, term: str) -> float:
        n = len(self._docs)
        df = self._df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        q_terms = tokenize(query)
        scores: list[tuple[str, float]] = []
        for cid, toks in zip(self._docs, self._tokens, strict=True):
            if not toks:
                continue
            tf = Counter(toks)
            dl = len(toks)
            score = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                f = tf[term]
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self._avg_len or 1))
                score += self._idf(term) * (f * (self.k1 + 1)) / denom
            if score > 0:
                scores.append((cid, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
