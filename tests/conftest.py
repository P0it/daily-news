"""공통 pytest fixtures."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def memory_db() -> sqlite3.Connection:
    """테스트용 in-memory SQLite. 매 테스트마다 새로 생성."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
