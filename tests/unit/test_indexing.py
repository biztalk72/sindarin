"""E6 unit tests: chunker, embedder, BM25, in-memory vector store, embedding worker."""

from uuid import uuid4

from document_ir import Block, BlockType, DocumentIR, DocumentType, Quality, TableSchema
from embedding_worker import acl_hash_for, activate, collection_name, index
from hybrid_idp_shared import SecurityLevel
from rag_core import (
    BM25Index,
    DeterministicEmbedder,
    InMemoryVectorStore,
    chunk_document,
)


def _ir() -> DocumentIR:
    return DocumentIR(
        document_id=uuid4(),
        source_uri="s3://x/doc.docx",
        document_type=DocumentType.DOCX,
        blocks=[
            Block(block_id="h1", block_type=BlockType.HEADING, text="계약", page_no=1, section_path=["계약"]),
            Block(block_id="p1", block_type=BlockType.PARAGRAPH, text="위약금은 100만원이다.", page_no=1, section_path=["계약"]),
            Block(
                block_id="t1",
                block_type=BlockType.TABLE,
                text="구분 | 금액",
                page_no=1,
                section_path=["계약"],
                table_schema=TableSchema(headers=["구분", "금액"], rows=[["해지", "100"]]),
            ),
            Block(block_id="p2", block_type=BlockType.PARAGRAPH, text="부칙 내용", page_no=2, section_path=["부칙"]),
        ],
        quality=Quality(parser="markitdown"),
    )


# --- chunker ---

def test_table_is_its_own_chunk_and_pages_split() -> None:
    chunks = chunk_document(_ir())
    assert len(chunks) == 3
    assert chunks[0].page_no == 1 and "위약금" in chunks[0].text  # heading+para merged
    assert chunks[1].block_refs == ["t1"]  # table isolated
    assert "해지" in chunks[1].text
    assert chunks[2].page_no == 2  # page boundary split
    assert chunks[0].toc_path == ["계약"]


# --- embedder ---

def test_deterministic_embedder_is_stable_and_normalized() -> None:
    e = DeterministicEmbedder(dim=32)
    v1 = e.embed(["계약 위약금"])[0]
    v2 = e.embed(["계약 위약금"])[0]
    assert v1 == v2
    assert len(v1) == 32
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-9


# --- BM25 ---

def test_bm25_exact_term_ranks_first() -> None:
    idx = BM25Index()
    idx.index([("c1", "계약 해지 위약금 조항"), ("c2", "급여 명세서 내용"), ("c3", "위약금 산정 기준")])
    hits = idx.search("위약금", top_k=3)
    assert hits[0][0] in {"c1", "c3"}
    assert all(cid != "c2" for cid, _ in hits)


# --- in-memory store ---

def test_in_memory_store_search_and_acl_filter() -> None:
    store = InMemoryVectorStore()
    store.ensure_collection("c", 3)
    store.upsert(
        "c",
        [
            ("a", [1.0, 0.0, 0.0], {"security_level": "public"}),
            ("b", [0.0, 1.0, 0.0], {"security_level": "confidential"}),
        ],
    )
    hits = store.search("c", [1.0, 0.0, 0.0], top_k=2)
    assert hits[0].chunk_id == "a"
    filtered = store.search("c", [0.0, 1.0, 0.0], payload_filter={"security_level": ["public"]})
    assert [h.chunk_id for h in filtered] == ["a"]  # 'b' filtered out by ACL scope


# --- embedding worker ---

def test_index_produces_payloads_and_is_searchable() -> None:
    ir = _ir()
    store = InMemoryVectorStore()
    embedder = DeterministicEmbedder(dim=48)
    payloads = index(
        ir,
        embedder=embedder,
        store=store,
        base_collection="docs",
        embedding_model="det-48",
        embedding_version="v1",
        security_level=SecurityLevel.INTERNAL,
        acl_hash=acl_hash_for(["user-1", "admin"]),
    )
    assert len(payloads) == 3
    assert {p.embedding_version for p in payloads} == {"v1"}
    assert all(p.page_no is not None for p in payloads)

    name = collection_name("docs", "v1")
    qv = embedder.embed(["위약금 100만원"])[0]
    hits = store.search(name, qv, top_k=3)
    assert hits and hits[0].payload["embedding_model"] == "det-48"


def test_blue_green_alias_activate() -> None:
    ir = _ir()
    store = InMemoryVectorStore()
    embedder = DeterministicEmbedder(dim=16)
    index(
        ir, embedder=embedder, store=store, base_collection="docs",
        embedding_model="det", embedding_version="v2",
        security_level=SecurityLevel.PUBLIC, acl_hash="h",
    )
    activate(store, alias="docs", base_collection="docs", embedding_version="v2")
    assert store.resolve("docs") == "docs__v2"
    hits = store.search("docs", embedder.embed(["부칙"])[0], top_k=1)  # via alias
    assert hits
