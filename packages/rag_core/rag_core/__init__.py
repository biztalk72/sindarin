"""RAG core — hybrid retrieval + trust pipeline (ADR-0008, PRD2 §7).

Pipeline order (PRD2 §7): query understanding → scope resolution → ACL filtering →
vector search + BM25/keyword → reranking → context packing → answer generation →
citation validation → runtime eval. PageIndex is the structure/citation aid, not the sole
retrieval primitive.
"""

from rag_core.chunker import Chunk, chunk_document
from rag_core.embedder import DeterministicEmbedder, Embedder, OpenAIEmbedder
from rag_core.generator import DeterministicGenerator, Generator, OpenAIGenerator
from rag_core.guardrails import (
    PiiMatch,
    detect_injection,
    detect_pii,
    redact_pii,
    strip_injection,
)
from rag_core.keyword_index import BM25Index, tokenize
from rag_core.payload import ChunkPayload
from rag_core.pipeline import (
    ChatResult,
    Citation,
    RagPipeline,
    detect_language,
    pack_context,
    route_model,
)
from rag_core.retrieval import (
    Authorizer,
    Candidate,
    ChunkRecord,
    acl_filter,
    hybrid_retrieve,
)
from rag_core.trust import AnswerDraft, Claim, TrustOutcome, validate_citations
from rag_core.vectorstore import Hit, InMemoryVectorStore, QdrantVectorStore, VectorStore

__all__ = [
    "ChunkPayload",
    "Chunk",
    "chunk_document",
    "Embedder",
    "DeterministicEmbedder",
    "OpenAIEmbedder",
    "BM25Index",
    "tokenize",
    "VectorStore",
    "InMemoryVectorStore",
    "QdrantVectorStore",
    "Hit",
    # retrieval
    "ChunkRecord",
    "Candidate",
    "Authorizer",
    "hybrid_retrieve",
    "acl_filter",
    # trust
    "AnswerDraft",
    "Claim",
    "TrustOutcome",
    "validate_citations",
    # generation
    "Generator",
    "DeterministicGenerator",
    "OpenAIGenerator",
    # guardrails
    "PiiMatch",
    "detect_pii",
    "redact_pii",
    "detect_injection",
    "strip_injection",
    # pipeline
    "RagPipeline",
    "ChatResult",
    "Citation",
    "pack_context",
    "detect_language",
    "route_model",
]
