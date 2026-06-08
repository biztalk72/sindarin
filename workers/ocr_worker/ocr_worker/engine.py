"""OCR engine seam (OCR-002/003/004, ADR-0009).

The real engines (PaddleOCR text + PaddleOCR-VL layout) need GPU models and PDF rendering,
which are env-blocked here, so they live behind a protocol with a not-yet-runnable real impl.
Tests inject a fake engine returning ``OcrPage``s. These are preprocessing engines, exempt
from ADR-0001 (ADR-0009).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class OcrLine:
    text: str
    confidence: float
    bbox: dict[str, Any] | None = None  # {x,y,w,h} normalized


@dataclass
class OcrPage:
    page_no: int
    lines: list[OcrLine] = field(default_factory=list)


class OcrEngine(Protocol):
    """Render + recognize a PDF/image into per-page OCR lines."""

    def recognize(self, source_uri: str) -> list[OcrPage]: ...


class PaddleOcrEngine:
    """Real PaddleOCR / PaddleOCR-VL engine (ADR-0009). Env-blocked in this environment."""

    def __init__(self, *, use_vl: bool = True, dpi: int = 200) -> None:
        self.use_vl = use_vl
        self.dpi = dpi

    def recognize(self, source_uri: str) -> list[OcrPage]:
        raise NotImplementedError(
            "PaddleOCR(-VL) requires the paddle stack + PDF rendering (OCR-002/003/004). "
            "Implement render→OCR/layout here; behind this protocol so the IR-shaping and "
            "quality gate are already tested."
        )
