"""Shared test fixtures. Golden documents live in tests/fixtures/."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
