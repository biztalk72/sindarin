"""Vector store abstraction (E6, ADR-0008).

Used by the embedding worker (writes) and retrieval (reads). ``payload_filter`` applies the
ACL/metadata scope at search time (the vector-side of the ACL double-check, PRD2 §10.1; the
authoritative per-document check is Postgres in E7). Blue/green reindex is modeled with
collection aliases: index into ``name_v2``, then ``set_alias(alias, name_v2)``.

Two impls: ``InMemoryVectorStore`` (dependency-free, unit tests) and ``QdrantVectorStore``
(the provisional dev backend). Both share the protocol so callers don't care which is live.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Hit:
    chunk_id: str
    score: float
    payload: dict[str, Any]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _matches(payload: dict[str, Any], payload_filter: dict[str, list[Any]] | None) -> bool:
    if not payload_filter:
        return True
    for field, allowed in payload_filter.items():
        if payload.get(field) not in allowed:
            return False
    return True


class VectorStore(Protocol):
    def ensure_collection(self, name: str, dim: int) -> None: ...
    def upsert(self, name: str, points: list[tuple[str, list[float], dict[str, Any]]]) -> None: ...
    def search(
        self,
        name: str,
        vector: list[float],
        top_k: int = 10,
        payload_filter: dict[str, list[Any]] | None = None,
    ) -> list[Hit]: ...
    def set_alias(self, alias: str, collection: str) -> None: ...
    def resolve(self, alias: str) -> str: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._cols: dict[str, dict[str, tuple[list[float], dict[str, Any]]]] = {}
        self._aliases: dict[str, str] = {}

    def ensure_collection(self, name: str, dim: int) -> None:  # noqa: ARG002
        self._cols.setdefault(name, {})

    def upsert(self, name: str, points: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        col = self._cols.setdefault(name, {})
        for chunk_id, vec, payload in points:
            col[chunk_id] = (vec, payload)

    def search(
        self,
        name: str,
        vector: list[float],
        top_k: int = 10,
        payload_filter: dict[str, list[Any]] | None = None,
    ) -> list[Hit]:
        col = self._cols.get(self._aliases.get(name, name), {})
        scored = [
            Hit(chunk_id=cid, score=_cosine(vector, vec), payload=payload)
            for cid, (vec, payload) in col.items()
            if _matches(payload, payload_filter)
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    def set_alias(self, alias: str, collection: str) -> None:
        self._aliases[alias] = collection

    def resolve(self, alias: str) -> str:
        return self._aliases.get(alias, alias)


class QdrantVectorStore:
    """Provisional dev backend (Qdrant running on :6333). Lazy client import."""

    def __init__(self, url: str = "http://localhost:6333") -> None:
        self._url = url
        self._client: Any = None
        self._ns = uuid.UUID("00000000-0000-0000-0000-00000000d00d")

    def _c(self) -> Any:
        if self._client is None:
            from qdrant_client import QdrantClient  # lazy

            self._client = QdrantClient(url=self._url)
        return self._client

    def _point_id(self, chunk_id: str) -> str:
        return str(uuid.uuid5(self._ns, chunk_id))

    def ensure_collection(self, name: str, dim: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        client = self._c()
        if not client.collection_exists(name):
            client.create_collection(
                name, vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
            )

    def upsert(self, name: str, points: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        from qdrant_client.models import PointStruct

        self._c().upsert(
            collection_name=name,
            points=[
                PointStruct(
                    id=self._point_id(cid), vector=vec, payload={**payload, "chunk_id": cid}
                )
                for cid, vec, payload in points
            ],
        )

    def search(
        self,
        name: str,
        vector: list[float],
        top_k: int = 10,
        payload_filter: dict[str, list[Any]] | None = None,
    ) -> list[Hit]:
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        qfilter = None
        if payload_filter:
            qfilter = Filter(
                must=[
                    FieldCondition(key=k, match=MatchAny(any=list(v)))
                    for k, v in payload_filter.items()
                ]
            )
        res = (
            self._c()
            .query_points(
                collection_name=self.resolve(name),
                query=vector,
                limit=top_k,
                query_filter=qfilter,
                with_payload=True,
            )
            .points
        )
        return [
            Hit(chunk_id=p.payload.get("chunk_id", str(p.id)), score=p.score, payload=p.payload)
            for p in res
        ]

    def set_alias(self, alias: str, collection: str) -> None:
        self._c().update_collection_aliases(
            change_aliases_operations=[
                {"create_alias": {"collection_name": collection, "alias_name": alias}}
            ]
        )

    def resolve(self, alias: str) -> str:
        return alias  # Qdrant resolves aliases server-side at query time
