"""E7 wiring: settings-driven pipeline factory (app.rag)."""

from app.config import Settings
from app.rag import build_embedder, build_generator, build_pipeline, openai_configured
from rag_core import BM25Index, OpenAIEmbedder, OpenAIGenerator, RagPipeline


def _settings(**over) -> Settings:
    base = {"openai_api_key": "k", "embedding_model": "embed-m", "answer_model": "ans-m"}
    base.update(over)
    return Settings(**base)


def test_openai_configured_gate() -> None:
    assert openai_configured(Settings(openai_api_key="", embedding_model="")) is False
    assert openai_configured(Settings(openai_api_key="k", embedding_model="")) is False
    assert openai_configured(_settings()) is True


def test_build_embedder_and_generator_from_settings() -> None:
    s = _settings(embedding_base_url="", openai_base_url="http://llm/v1", embedding_dim=256)
    emb = build_embedder(s)
    gen = build_generator(s)
    assert isinstance(emb, OpenAIEmbedder)
    assert emb.model == "embed-m"
    assert emb.dim == 256
    assert emb._base_url == "http://llm/v1"  # embedding_base_url falls back to openai_base_url
    assert isinstance(gen, OpenAIGenerator)
    assert gen.model == "ans-m"


def test_build_pipeline_assembles_real_components() -> None:
    class _Authorizer:
        def allowed_documents(self, principals):  # noqa: ARG002
            return None

    pipeline = build_pipeline(
        corpus={},
        bm25=BM25Index(),
        authorizer=_Authorizer(),
        s=_settings(vector_collection="docs"),
    )
    assert isinstance(pipeline, RagPipeline)
    assert isinstance(pipeline.embedder, OpenAIEmbedder)
    assert isinstance(pipeline.generator, OpenAIGenerator)
    assert pipeline.collection == "docs"
