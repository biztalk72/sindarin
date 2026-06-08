"""E6 integration: QdrantVectorStore against a live Qdrant (infra/compose dev stack).

Skips automatically if Qdrant isn't reachable, so the unit suite stays hermetic. Run with the
dev stack up: `make up` (Qdrant on :6333). Marked `integration`.
"""

import os

import pytest
from rag_core import QdrantVectorStore

pytestmark = pytest.mark.integration

QDRANT_URL = os.environ.get("VECTOR_DB_URL_EXTERNAL", "http://localhost:6333")
COLLECTION = "hybrid_idp_test_e6"


@pytest.fixture
def store() -> QdrantVectorStore:
    s = QdrantVectorStore(url=QDRANT_URL)
    try:
        client = s._c()
        client.get_collections()  # connectivity probe
    except Exception:  # noqa: BLE001
        pytest.skip("Qdrant not reachable on " + QDRANT_URL)
    yield s
    try:
        s._c().delete_collection(COLLECTION)
    except Exception:  # noqa: BLE001
        pass


def test_ensure_upsert_search_roundtrip(store: QdrantVectorStore) -> None:
    store.ensure_collection(COLLECTION, dim=3)
    store.upsert(
        COLLECTION,
        [
            ("chk_a", [1.0, 0.0, 0.0], {"security_level": "public", "page_no": 1}),
            ("chk_b", [0.0, 1.0, 0.0], {"security_level": "confidential", "page_no": 2}),
        ],
    )
    hits = store.search(COLLECTION, [1.0, 0.0, 0.0], top_k=2)
    assert hits[0].chunk_id == "chk_a"
    assert hits[0].payload["page_no"] == 1


def test_payload_filter_enforces_acl_scope(store: QdrantVectorStore) -> None:
    store.ensure_collection(COLLECTION, dim=3)
    store.upsert(
        COLLECTION,
        [
            ("chk_a", [1.0, 0.0, 0.0], {"security_level": "public"}),
            ("chk_b", [0.9, 0.1, 0.0], {"security_level": "confidential"}),
        ],
    )
    hits = store.search(
        COLLECTION, [1.0, 0.0, 0.0], top_k=5, payload_filter={"security_level": ["public"]}
    )
    assert [h.chunk_id for h in hits] == ["chk_a"]  # confidential filtered out
