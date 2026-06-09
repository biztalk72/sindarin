"""Runtime guardrails (E8, ADR-0006, PRD2 §7.1/§10.1).

Deterministic, dependency-free filters that run on the chat choke point:
- **PII** (EN+KO): email, phone, 주민등록번호(RRN), 사업자등록번호, credit card → detect + redact.
- **Prompt injection**: strip injected instructions from retrieved document text before it
  reaches the model, and flag detected attempts.

Presidio (spaCy NER) is the heavier ADR-0006 upgrade for PII; these regexes are the always-on
runtime layer (fast, testable, Korean-aware). The LLM-judge output filter is a follow-up that
plugs in alongside the PII output scan here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --- PII patterns (ordered: most specific first so redaction doesn't overlap badly) ---
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("rrn", re.compile(r"\b\d{6}-?[1-4]\d{6}\b")),  # 주민등록번호
    ("biz_no", re.compile(r"\b\d{3}-\d{2}-\d{5}\b")),  # 사업자등록번호
    ("credit_card", re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("phone", re.compile(r"\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b")),
]

# --- Prompt-injection signatures (EN + KO) ---
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?(above|previous|system)", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"^\s*(system|assistant)\s*:", re.I | re.M),
    re.compile(r"이전\s*(의\s*)?지시.{0,6}(무시|무효)"),
    re.compile(r"위\s*내용.{0,4}무시"),
    re.compile(r"(다음|아래)\s*지시.{0,6}따르"),
]


@dataclass
class PiiMatch:
    type: str
    value: str


def list_pii_policies() -> list[dict[str, str]]:
    """Public read view of the PII patterns — admin Guardrails page (GP3 read-only)."""
    return [{"name": name, "pattern": pat.pattern} for name, pat in _PII_PATTERNS]


def list_injection_policies() -> list[dict[str, str]]:
    """Public read view of the injection patterns — admin Guardrails page (GP3 read-only)."""
    return [{"pattern": pat.pattern} for pat in _INJECTION_PATTERNS]


def detect_pii(text: str) -> list[PiiMatch]:
    found: list[PiiMatch] = []
    for kind, pat in _PII_PATTERNS:
        for m in pat.finditer(text):
            found.append(PiiMatch(type=kind, value=m.group(0)))
    return found


def redact_pii(text: str) -> tuple[str, list[PiiMatch]]:
    matches: list[PiiMatch] = []
    redacted = text
    for kind, pat in _PII_PATTERNS:
        def _sub(m: re.Match[str], _k: str = kind) -> str:
            matches.append(PiiMatch(type=_k, value=m.group(0)))
            return f"[REDACTED:{_k}]"

        redacted = pat.sub(_sub, redacted)
    return redacted, matches


def detect_injection(text: str) -> list[str]:
    hits: list[str] = []
    for pat in _INJECTION_PATTERNS:
        m = pat.search(text)
        if m:
            hits.append(m.group(0).strip())
    return hits


def strip_injection(text: str) -> tuple[str, list[str]]:
    """Remove sentences/lines that contain injection signatures from document text."""
    removed: list[str] = []
    kept_lines: list[str] = []
    for line in text.splitlines():
        if any(p.search(line) for p in _INJECTION_PATTERNS):
            removed.append(line.strip())
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines), removed
