"""Semantic keyword extraction (HWPX-005, PRD2 §5.4).

Lightweight Korean-document regex extractors for the keyword classes the PRD calls out:
법령명 / 제N조, 날짜, 금액, 기관명. Frequency becomes a coarse weight. Not exhaustive — a
deliberately cheap pass that feeds the word cloud / keyword graph (E10) and query expansion.
"""

from __future__ import annotations

import re
from collections import Counter

from document_ir import SemanticKeyword

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("법령명", re.compile(r"[가-힣]{2,}법(?:률)?")),
    ("법령명", re.compile(r"제\d+조(?:의\d+)?")),
    ("기관명", re.compile(r"[가-힣]{2,}(?:부|청|위원회|공사|공단|원|처)")),
    ("날짜", re.compile(r"\d{4}-\d{2}-\d{2}")),
    ("날짜", re.compile(r"\d{4}년\s?\d{1,2}월(?:\s?\d{1,2}일)?")),
    ("금액", re.compile(r"[\d,]+\s?(?:억|만)?\s?원")),
]


def extract_keywords(text: str, *, max_keywords: int = 50) -> list[SemanticKeyword]:
    counts: Counter[tuple[str, str]] = Counter()
    for kind, pat in _PATTERNS:
        for m in pat.findall(text):
            kw = m.strip()
            if kw:
                counts[(kind, kw)] += 1

    if not counts:
        return []

    top = counts.most_common(max_keywords)
    max_count = top[0][1]
    return [
        SemanticKeyword(keyword=kw, kind=kind, weight=round(count / max_count, 3))
        for (kind, kw), count in top
    ]
