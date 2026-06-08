"""Document metadata extraction (HWPX-004, PRD2 §5.4).

Best-effort: reads Dublin-Core-ish fields from ``content.hpf`` (the OWPML package descriptor)
by local element name, so namespace variance is tolerated. Missing fields are simply absent.
A ``security_label`` candidate is surfaced when present for the ACL pipeline (PRD2 §10.1).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

_FIELD_BY_LOCAL = {
    "creator": "author",
    "author": "author",
    "date": "created_at",
    "title": "title",
    "subject": "subject",
}


def extract_metadata(content_hpf: str | None) -> dict[str, str]:
    if not content_hpf:
        return {}
    try:
        root = ET.fromstring(content_hpf)
    except ET.ParseError:
        return {}

    meta: dict[str, str] = {}
    for el in root.iter():
        local = el.tag.rsplit("}", 1)[-1].lower()
        txt = (el.text or "").strip()
        if local in _FIELD_BY_LOCAL and txt:
            meta.setdefault(_FIELD_BY_LOCAL[local], txt)
        if local in ("security", "seclevel", "securitylevel") and txt:
            meta.setdefault("security_label", txt)
    return meta
