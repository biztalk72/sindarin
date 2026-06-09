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


def _parse_draft(content: str) -> AnswerDraft | None:
    """Parse the model's JSON output into an ``AnswerDraft``.

    Returns ``None`` if the content isn't valid JSON-with-claims, so the caller can decide
    whether to retry. Distinct from "parsed but no claims" (which is a valid empty draft).
    """
    import json

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or "claims" not in data:
        return None
    claims = []
    for item in data.get("claims", []):
        if not isinstance(item, dict):
            continue
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
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Question: {query}\n\nContext:\n{_build_context(candidates)}",
            },
        ]
        # RAG answers are citation-bound and short; without a cap, vLLM defaults to
        # `max_model_len - prompt_tokens` (~7800 on a 14B/8k), and verbose generations can
        # wallclock minutes. 768 covers any reasonable cited answer well under the upstream
        # proxy timeout.
        common = {
            "model": self.model,
            "max_tokens": 768,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        resp = client.chat.completions.create(temperature=self._temperature, **common)
        draft = _parse_draft(resp.choices[0].message.content)
        if draft is not None:
            return draft

        # Retry once with a small temperature bump. Anticipates the smaller-model case
        # (ADR-0011 Nemotron-Nano-8B) where JSON adherence is occasionally brittle; the
        # retry costs ~0.5–1× a normal call and only fires on the unhappy path.
        import logging

        logging.getLogger(__name__).warning(
            "generator: model returned non-JSON, retrying with temp=0.2 (model=%s)", self.model,
        )
        resp = client.chat.completions.create(temperature=0.2, **common)
        draft = _parse_draft(resp.choices[0].message.content)
        if draft is not None:
            draft.model_outcome = "json_retry"
            return draft

        logging.getLogger(__name__).warning(
            "generator: JSON retry also failed; dropping answer (model=%s)", self.model,
        )
        return AnswerDraft(claims=[], model_outcome="json_failed")
