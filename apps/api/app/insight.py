"""Document insight computations (E10, PRD2 §8.3).

Pure functions over persisted chunk data so they're testable without a DB:
- ``build_toc``      — nest section paths into a tree (UI-DOC insight / TOC).
- ``compute_keywords`` — frequency keyword list (a simplified stand-in for the full hybrid
  TF-IDF/BM25/embedding/style score, PRD2 §8.3; merges persisted semantic keywords).
- ``build_graph``    — keyword co-occurrence graph (node cap 20–50, edge cap 150, §8.3).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from rag_core import tokenize

# Tiny stopword set; real KO/EN stopword handling is a follow-up.
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on", "with",
    "이", "그", "저", "수", "등", "및", "또는", "하다", "있다",
}
MAX_NODES = 30
MAX_EDGES = 150


def build_toc(items: list[tuple[list[str], int | None]]) -> list[dict[str, Any]]:
    """items: (section_path, page_no) in document order → nested TOC tree."""
    roots: list[dict[str, Any]] = []
    index: dict[tuple[str, ...], dict[str, Any]] = {}
    for path, page in items:
        for depth in range(len(path)):
            key = tuple(path[: depth + 1])
            if key in index:
                continue
            node: dict[str, Any] = {"title": path[depth], "page_no": page, "children": []}
            index[key] = node
            if depth == 0:
                roots.append(node)
            else:
                index[tuple(path[:depth])]["children"].append(node)
    return roots


def _terms(text: str) -> list[str]:
    return [t for t in tokenize(text) if len(t) >= 2 and t not in _STOP]


def compute_keywords(
    texts: list[str],
    persisted: list[tuple[str, float | None, str | None]] | None = None,
    *,
    top_n: int = MAX_NODES,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(set(_terms(text)))  # document-frequency style weighting

    persisted_map = {kw: (w, kind) for kw, w, kind in (persisted or [])}
    if not counts and not persisted_map:
        return []

    max_count = max(counts.values()) if counts else 1
    merged: dict[str, dict[str, Any]] = {}
    for kw, c in counts.most_common(top_n):
        merged[kw] = {"keyword": kw, "weight": round(c / max_count, 3), "kind": None}
    for kw, (w, kind) in persisted_map.items():
        merged[kw] = {"keyword": kw, "weight": w if w is not None else 1.0, "kind": kind}

    out = sorted(merged.values(), key=lambda k: k["weight"] or 0, reverse=True)
    return out[:top_n]


def build_graph(
    texts: list[str],
    keywords: list[str],
    *,
    max_nodes: int = MAX_NODES,
    max_edges: int = MAX_EDGES,
) -> dict[str, Any]:
    nodes = keywords[:max_nodes]
    node_set = set(nodes)
    pair_counts: Counter[tuple[str, str]] = Counter()
    for text in texts:
        present = sorted(node_set & set(_terms(text)))
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                pair_counts[(present[i], present[j])] += 1

    edges = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in pair_counts.most_common(max_edges)
    ]
    return {
        "nodes": [{"id": n, "label": n} for n in nodes],
        "edges": edges,
    }
