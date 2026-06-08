"""PDF classifier (OCR-001, PRD2 §5.3).

Decides the processing path by text-layer coverage: ``digital`` (born-digital text layer →
extract directly), ``scanned`` (image-only → render + OCR), or ``hybrid`` (mixed → OCR the
image pages). The ratio computation is pure and injectable so it's testable without real
PDFs; ``classify_pdf`` is thin pypdf glue around it.
"""

from __future__ import annotations

from typing import Literal, Protocol

PdfKind = Literal["digital", "scanned", "hybrid"]

DIGITAL_THRESHOLD = 0.8
SCANNED_THRESHOLD = 0.2
MIN_TEXT_CHARS = 20  # a page needs at least this many chars to count as "has text"


class PageTextExtractor(Protocol):
    def __call__(self, source_path: str) -> list[str]: ...


def classify_from_page_texts(
    page_texts: list[str],
    *,
    digital_threshold: float = DIGITAL_THRESHOLD,
    scanned_threshold: float = SCANNED_THRESHOLD,
) -> PdfKind:
    if not page_texts:
        return "scanned"
    with_text = sum(1 for t in page_texts if len(t.strip()) >= MIN_TEXT_CHARS)
    ratio = with_text / len(page_texts)
    if ratio >= digital_threshold:
        return "digital"
    if ratio <= scanned_threshold:
        return "scanned"
    return "hybrid"


def _pypdf_page_texts(source_path: str) -> list[str]:
    from pypdf import PdfReader  # lazy

    reader = PdfReader(source_path)
    return [(page.extract_text() or "") for page in reader.pages]


def classify_pdf(source_path: str, *, extractor: PageTextExtractor | None = None) -> PdfKind:
    extract = extractor or _pypdf_page_texts
    return classify_from_page_texts(extract(source_path))
