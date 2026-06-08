"""Answer generation behind an injectable seam (E7, ADR-0001).

The real generator calls the OpenAI-compatible client (the model router rotates over these).
``DeterministicGenerator`` is an extractive, dependency-free generator for dev/tests: it emits
one claim per top candidate, each citing the chunk it was drawn from — so the trust layer can
verify citations end-to-end without a live LLM.
"""

from __future__ import annotations

from typing import Any, Protocol

from rag_core.retrieval import Candidate
from rag_core.trust import AnswerDraft, Claim


class Generator(Protocol):
    def generate(self, query: str, candidates: list[Candidate]) -> AnswerDraft: ...


def _first_sentence(text: str) -> str:
    for sep in (". ", "다.", "。", "\n"):
        idx = text.find(sep)
        if idx != -1:
            return text[: idx + len(sep)].strip()
    return text.strip()


class DeterministicGenerator:
    """Extractive: top-N candidates → claims citing their own chunk. No LLM."""

    def __init__(self, max_claims: int = 3) -> None:
        self.max_claims = max_claims

    def generate(self, query: str, candidates: list[Candidate]) -> AnswerDraft:  # noqa: ARG002
        claims = [
            Claim(text=_first_sentence(c.record.text), citations=[c.record.chunk_id])
            for c in candidates[: self.max_claims]
            if c.record.text.strip()
        ]
        return AnswerDraft(claims=claims)


_SYSTEM_PROMPT = (
    "You are a document-grounded assistant. Answer ONLY from the provided context passages, "
    "each labelled [chunk_id]. Decompose your answer into atomic claims. Every claim MUST cite "
    "the chunk_id(s) it is supported by. If the context does not answer the question, return no "
    "claims. Respond with JSON only: "
    '{"claims":[{"text":"<claim>","citations":["<chunk_id>",...]}]}. '
    "Answer in the same language as the question."
)


def _build_context(candidates: list[Candidate]) -> str:
    return "\n\n".join(f"[{c.record.chunk_id}] {c.record.text}" for c in candidates)


def _parse_draft(content: str) -> AnswerDraft:
    import json

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return AnswerDraft(claims=[])
    claims = []
    for item in data.get("claims", []) if isinstance(data, dict) else []:
        text = (item.get("text") or "").strip()
        cites = [str(c) for c in item.get("citations", []) if c]
        if text:
            claims.append(Claim(text=text, citations=cites))
    return AnswerDraft(claims=claims)


class OpenAIGenerator:
    """Real generator via the OpenAI-compatible client (ADR-0001).

    Emits claim-structured, per-claim-cited JSON; the trust layer then drops any claim whose
    citation doesn't hold (ADR-0004). The client is injectable (tests fake the transport);
    by default it is lazily constructed from ``base_url``/``api_key``.
    """

    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        client: object | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.model = model
        self._base_url = base_url
        self._api_key = api_key
        self._client = client
        self._temperature = temperature

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI  # lazy

            self._client = OpenAI(base_url=self._base_url, api_key=self._api_key)
        return self._client

    def generate(self, query: str, candidates: list[Candidate]) -> AnswerDraft:
        if not candidates:
            return AnswerDraft(claims=[])
        client = self._ensure_client()
        resp = client.chat.completions.create(
            model=self.model,
            temperature=self._temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Question: {query}\n\nContext:\n{_build_context(candidates)}",
                },
            ],
        )
        return _parse_draft(resp.choices[0].message.content)
