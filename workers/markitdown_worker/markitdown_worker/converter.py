"""Markdown conversion behind an injectable seam (ADR-0007).

The real converter lazily imports MarkItDown so the mapper stays pure and testable without
the binary; tests inject a fake. Same DI shape as ``pageindex`` summarizers.
"""

from __future__ import annotations

from typing import Any, Protocol


class MarkdownConverter(Protocol):
    """Converts a source file (path) to a Markdown string."""

    def convert(self, source_path: str) -> str: ...


class MarkItDownConverter:
    """Default converter — wraps Microsoft MarkItDown (lazy import)."""

    def __init__(self) -> None:
        self._md: Any = None

    def convert(self, source_path: str) -> str:
        if self._md is None:
            from markitdown import MarkItDown  # lazy: not needed for unit tests

            self._md = MarkItDown()
        return str(self._md.convert(source_path).text_content)
