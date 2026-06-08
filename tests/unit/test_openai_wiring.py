"""E7 wiring: real OpenAIEmbedder + OpenAIGenerator via a faked OpenAI transport.

Proves the real classes parse/produce correctly and plug into the full pipeline end-to-end —
only the HTTP transport is faked, the orchestration/trust logic is the real code path.
"""

import hashlib
from uuid import uuid4

from rag_core import (
    BM25Index,
    Candidate,
    ChunkRecord,
    InMemoryVectorStore,
    OpenAIEmbedder,
    OpenAIGenerator,
    RagPipeline,
)

# --- fake OpenAI transport ---------------------------------------------------


class _Emb:
    def __init__(self, vec: list[float]) -> None:
        self.embedding = vec


class _EmbResp:
    def __init__(self, data: list[_Emb]) -> None:
        self.data = data


class _FakeEmbeddings:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.calls = 0

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in text.lower().split():
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        return v

    def create(self, model: str, input: list[str]):  # noqa: A002 - mirrors OpenAI SDK
        self.calls += 1
        return _EmbResp([_Emb(self._vec(t)) for t in input])


class FakeEmbedClient:
    def __init__(self, dim: int) -> None:
        self.embeddings = _FakeEmbeddings(dim)


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _ChatResp:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _ChatResp(self.content)


class FakeChatClient:
    def __init__(self, content: str) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(content)})()


# --- embedder ---------------------------------------------------------------


def test_openai_embedder_batches_and_returns_vectors() -> None:
    client = FakeEmbedClient(dim=8)
    emb = OpenAIEmbedder(model="m", dim=8, client=client, batch_size=2)
    vecs = emb.embed(["alpha", "beta", "gamma"])
    assert len(vecs) == 3
    assert all(len(v) == 8 for v in vecs)
    assert client.embeddings.calls == 2  # batches of 2 + 1


# --- generator --------------------------------------------------------------


def _candidate(chunk_id: str, text: str) -> Candidate:
    return Candidate(
        record=ChunkRecord(chunk_id=chunk_id, text=text, document_id=uuid4()),
        score=1.0,
        sources=["keyword"],
    )


def test_openai_generator_parses_claims() -> None:
    content = '{"claims":[{"text":"위약금은 100만원이다","citations":["a0"]}]}'
    gen = OpenAIGenerator(model="m", client=FakeChatClient(content))
    draft = gen.generate("위약금?", [_candidate("a0", "계약 해지 시 위약금은 100만원이다.")])
    assert len(draft.claims) == 1
    assert draft.claims[0].citations == ["a0"]


def test_openai_generator_no_candidates_skips_call() -> None:
    client = FakeChatClient('{"claims":[]}')
    gen = OpenAIGenerator(model="m", client=client)
    assert gen.generate("q", []).claims == []
    assert client.chat.completions.last_kwargs is None  # no API call when nothing to ground on


def test_openai_generator_malformed_json_yields_no_claims() -> None:
    gen = OpenAIGenerator(model="m", client=FakeChatClient("not json at all"))
    assert gen.generate("q", [_candidate("a0", "text")]).claims == []


# --- end-to-end pipeline with the real classes ------------------------------


def test_pipeline_end_to_end_with_openai_classes() -> None:
    doc_a, doc_b = uuid4(), uuid4()
    corpus = {
        "a0": ChunkRecord(
            "a0", "계약 해지 시 위약금은 100만원이다.", doc_a, page_no=1, toc_path=["계약"]
        ),
        "b0": ChunkRecord(
            "b0", "급여는 매월 25일에 지급한다.", doc_b, page_no=1, toc_path=["급여"]
        ),
    }
    embedder = OpenAIEmbedder(model="m", dim=64, client=FakeEmbedClient(64))
    store = InMemoryVectorStore()
    store.ensure_collection("documents", 64)
    store.upsert(
        "documents",
        [
            (cid, embedder.embed([r.text])[0], {"document_id": str(r.document_id)})
            for cid, r in corpus.items()
        ],
    )
    bm25 = BM25Index()
    bm25.index([(cid, r.text) for cid, r in corpus.items()])

    gen = OpenAIGenerator(
        model="m",
        client=FakeChatClient('{"claims":[{"text":"위약금은 100만원이다","citations":["a0"]}]}'),
    )

    class _Authorizer:
        def allowed_documents(self, principals):  # noqa: ARG002
            return None

    pipeline = RagPipeline(
        embedder=embedder,
        store=store,
        bm25=bm25,
        corpus=corpus,
        authorizer=_Authorizer(),
        generator=gen,
        collection="documents",
    )
    res = pipeline.answer("위약금 얼마", principals={"admin"})
    assert "위약금" in res.answer
    assert res.citations and res.citations[0].document_id == doc_a
    assert res.confidence["groundedness"] > 0
