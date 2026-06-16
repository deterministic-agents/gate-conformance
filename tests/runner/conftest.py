"""
Pytest fixtures shared across runner tests.

Each test gets a fresh in-memory sqlite database. Fixture SQL is loaded
via SqliteAdapter.execute_script (which the fixture files are
self-contained for - they include their own CREATE TABLE statements).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from runner.adapters.sql import SqliteAdapter


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def adapter() -> SqliteAdapter:
    """Fresh in-memory sqlite adapter per test."""
    a = SqliteAdapter(":memory:")
    yield a
    a.close()


@pytest.fixture
def load_fixture(adapter: SqliteAdapter) -> Callable[[str], None]:
    """Return a callable that loads a named fixture file into the adapter."""

    def _load(filename: str) -> None:
        path = FIXTURES_DIR / filename
        adapter.execute_script(path.read_text())

    return _load


@pytest.fixture
def default_check_config() -> dict:
    """Config the runner would normally pass to each check."""
    from runner.config import DEFAULT_THRESHOLDS

    return {
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "table_name_overrides": {},
        "assessment_window_days": 30,
    }
