"""E10: insight computations (TOC tree, keywords, co-occurrence graph)."""

from app.insight import build_graph, build_toc, compute_keywords


def test_build_toc_nests_section_paths() -> None:
    items = [(["계약"], 1), (["계약", "해지"], 1), (["계약", "위약금"], 2), (["부칙"], 3)]
    tree = build_toc(items)
    assert [n["title"] for n in tree] == ["계약", "부칙"]
    gye = tree[0]
    assert [c["title"] for c in gye["children"]] == ["해지", "위약금"]
    assert gye["children"][1]["page_no"] == 2


def test_compute_keywords_frequency_and_filters() -> None:
    texts = ["위약금 위약금 계약 the a", "위약금 급여 명세"]
    kws = compute_keywords(texts, top_n=10)
    words = {k["keyword"] for k in kws}
    assert "위약금" in words
    assert "the" not in words and "a" not in words  # stopwords/short filtered
    # 위약금 appears in both docs → highest doc-frequency weight
    top = max(kws, key=lambda k: k["weight"])
    assert top["keyword"] == "위약금"


def test_compute_keywords_merges_persisted() -> None:
    kws = compute_keywords(["계약 내용"], persisted=[("개인정보 보호법", 0.95, "법령명")])
    law = next(k for k in kws if k["keyword"] == "개인정보 보호법")
    assert law["kind"] == "법령명"
    assert law["weight"] == 0.95


def test_build_graph_co_occurrence_edges() -> None:
    texts = ["위약금 계약 해지", "위약금 계약", "급여 명세"]
    graph = build_graph(texts, ["위약금", "계약", "해지", "급여"])
    node_ids = {n["id"] for n in graph["nodes"]}
    assert {"위약금", "계약"} <= node_ids
    # 위약금 & 계약 co-occur in two texts → an edge with weight 2
    edge = next(
        e for e in graph["edges"] if {e["source"], e["target"]} == {"위약금", "계약"}
    )
    assert edge["weight"] == 2
