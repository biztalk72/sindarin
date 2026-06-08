"""HWPX package access (HWPX-001).

HWPX is an OWPML ZIP: ``Contents/header.xml`` (styles), ``Contents/section*.xml`` (body),
``Contents/content.hpf`` (package metadata). We read by entry-name suffix so layout variance
across producers doesn't break us. Parse failures raise ``HwpxPackageError`` so the worker
can route to the render+OCR fallback (HWPX-006 / ADR-0003).
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field


class HwpxPackageError(Exception):
    """Raised when the HWPX package cannot be opened or has no body sections."""


@dataclass
class HwpxPackage:
    header_xml: str | None
    section_xmls: list[str] = field(default_factory=list)
    content_hpf: str | None = None


def open_package(source_path: str) -> HwpxPackage:
    try:
        zf = zipfile.ZipFile(source_path)
    except (zipfile.BadZipFile, FileNotFoundError, OSError) as exc:
        raise HwpxPackageError(f"cannot open HWPX zip: {exc}") from exc

    with zf:
        names = zf.namelist()

        def read(name: str) -> str:
            return zf.read(name).decode("utf-8", errors="replace")

        sections = sorted(
            n for n in names if "section" in n.lower() and n.lower().endswith(".xml")
        )
        if not sections:
            raise HwpxPackageError("HWPX has no Contents/section*.xml body")

        header = next((n for n in names if n.lower().endswith("header.xml")), None)
        hpf = next((n for n in names if n.lower().endswith(".hpf")), None)

        return HwpxPackage(
            header_xml=read(header) if header else None,
            section_xmls=[read(s) for s in sections],
            content_hpf=read(hpf) if hpf else None,
        )
