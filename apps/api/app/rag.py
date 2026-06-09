"""RAG pipeline assembly from settings (E7 wiring, ADR-0001/0008).

Builds a ``RagPipeline`` backed by the real OpenAI-compatible embedder + generator and the
Qdrant vector store. The corpus (chunk text), BM25 index, and authorizer come from the
ingestion/repository layer (E6 persistence + E9 upload), so they are passed in — the factory
owns model/store wiring, not data loading. ``openai_configured`` gates the chat endpoint:
until an endpoint is set (and documents ingested) the route stays an honest 503.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from rag_core import (
    Authorizer,
    BM25Index,
    ChunkRecord,
    DeterministicEmbedder,
    DeterministicGenerator,
    Embedder,
    Generator,
    OpenAIEmbedder,
    OpenAIGenerator,
    QdrantVectorStore,
    RagPipeline,
)
from sqlalchemy.orm import Session

from app.config import Settings, settings

# Dev fallback dimensions/labels (offline mode: deterministic embed + extractive generate).
_DEV_DIM = 64
_DEV_EMBED_MODEL = "deterministic-bow"
_EMBED_VERSION = "v1"


@lru_cache(maxsize=4)
def _get_tokenizer(model_id: str) -> Any | None:
    """Lazy, cached chat-model tokenizer for token-aware ``pack_context`` (ADR-0011).

    Returns ``None`` if `tokenizers` isn't available or the model id can't be resolved —
    callers must treat None as "skip token budgeting, use the glyph fallback". The
    api.Dockerfile pre-fetches the configured model so the first request stays fast.
    """
    if not model_id:
        return None
    try:
        from tokenizers import Tokenizer
    except ImportError:  # `tokenizers` not installed → glyph fallback
        return None
    try:
        return Tokenizer.from_pretrained(model_id)
    except Exception as exc:  # noqa: BLE001 — network/auth/missing tokenizer.json all OK to silence
        logging.getLogger(__name__).warning(
            "tokenizer load failed for %s (%s); falling back to glyph budget", model_id, exc,
        )
        return None


def openai_configured(s: Settings = settings) -> bool:
    return bool(s.openai_api_key) and bool(s.embedding_model)


def select_embedder(s: Settings = settings, *, client: object | None = None) -> Embedder:
    """OpenAI embedder when configured; otherwise the deterministic dev embedder."""
    if openai_configured(s):
        return build_embedder(s, client=client)
    return DeterministicEmbedder(dim=_DEV_DIM)


def select_generator(s: Settings = settings, *, client: object | None = None) -> Generator:
    """OpenAI generator when configured; otherwise the extractive dev generator."""
    if openai_configured(s):
        return build_generator(s, client=client)
    return DeterministicGenerator()


def embedding_descriptor(s: Settings = settings) -> tuple[str, str]:
    """(embedding_model, embedding_version) recorded in the payload."""
    if openai_configured(s):
        return s.embedding_model, _EMBED_VERSION
    return _DEV_EMBED_MODEL, _EMBED_VERSION


def embedder_dim(s: Settings = settings) -> int:
    return s.embedding_dim if openai_configured(s) else _DEV_DIM


def build_embedder(s: Settings = settings, *, client: object | None = None) -> OpenAIEmbedder:
    return OpenAIEmbedder(
        model=s.embedding_model,
        dim=s.embedding_dim,
        base_url=s.embedding_base_url or s.openai_base_url,
        api_key=s.openai_api_key,
        client=client,
    )


def build_generator(s: Settings = settings, *, client: object | None = None) -> OpenAIGenerator:
    return OpenAIGenerator(
        model=s.answer_model,
        base_url=s.openai_base_url,
        api_key=s.openai_api_key,
        client=client,
    )


def build_pipeline(
    *,
    corpus: dict[str, ChunkRecord],
    bm25: BM25Index,
    authorizer: Authorizer,
    s: Settings = settings,
    embed_client: object | None = None,
    gen_client: object | None = None,
) -> RagPipeline:
    """Assemble a pipeline from a given corpus/bm25/authorizer (OpenAI or dev components)."""
    tokenizer = _get_tokenizer(s.chat_model) if s.chat_model else None
    return RagPipeline(
        embedder=select_embedder(s, client=embed_client),
        store=QdrantVectorStore(url=s.vector_db_url),
        bm25=bm25,
        corpus=corpus,
        authorizer=authorizer,
        generator=select_generator(s, client=gen_client),
        collection=s.vector_collection,
        tokenizer=tokenizer,
        budget_tokens=s.rag_context_token_budget if tokenizer is not None else None,
    )


def build_pipeline_from_db(session: Session, s: Settings = settings) -> RagPipeline:
    """Load the corpus + ACL from Postgres and assemble the live pipeline."""
    # Imported here to keep rag_core free of the app's DB layer.
    from app.repository import PostgresAuthorizer, build_bm25, load_corpus

    corpus = load_corpus(session)
    tokenizer = _get_tokenizer(s.chat_model) if s.chat_model else None
    return RagPipeline(
        embedder=select_embedder(s),
        store=QdrantVectorStore(url=s.vector_db_url),
        bm25=build_bm25(corpus),
        corpus=corpus,
        authorizer=PostgresAuthorizer(session),
        generator=select_generator(s),
        collection=s.vector_collection,
        tokenizer=tokenizer,
        budget_tokens=s.rag_context_token_budget if tokenizer is not None else None,
    )
