"""Embedding generation behind an injectable seam (E6, ADR-0008).

The real embedder uses the OpenAI-compatible client (ADR-0001); the embedding *model* is a
deferred follow-up ADR (PRD2 §15). ``DeterministicEmbedder`` is a dependency-free,
process-stable embedder (hashed bag-of-tokens) for dev and tests — same vector for the same
text every run, so similarity assertions are reproducible.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Protocol

_TOKEN = re.compile(r"[0-9a-zA-Z]+|[가-힣]+")


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DeterministicEmbedder:
    """Hashed bag-of-tokens → L2-normalized vector. Deterministic across processes."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in _TOKEN.findall(text.lower()):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            v[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0.0:
            return v
        return [x / norm for x in v]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


class OpenAIEmbedder:
    """Real embedder via the OpenAI-compatible client (ADR-0001).

    The client is injectable (tests pass a fake transport); by default it is lazily
    constructed from ``base_url``/``api_key``. Embeds in batches to respect endpoint limits.
    """

    def __init__(
        self,
        model: str,
        *,
        dim: int,
        base_url: str | None = None,
        api_key: str | None = None,
        client: object | None = None,
        batch_size: int = 128,
    ) -> None:
        self.model = model
        self.dim = dim
        self._base_url = base_url
        self._api_key = api_key
        self._client = client
        self._batch_size = batch_size

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI  # lazy

            self._client = OpenAI(base_url=self._base_url, api_key=self._api_key)
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._ensure_client()
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            resp = client.embeddings.create(model=self.model, input=batch)
            out.extend(d.embedding for d in resp.data)
        return out
