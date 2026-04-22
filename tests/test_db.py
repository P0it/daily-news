from __future__ import annotations

import sqlite3

import pytest

from news_briefing.storage.db import init_schema


def test_init_schema_creates_seen_and_cache_tables(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    rows = memory_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = [r["name"] for r in rows]
    assert "seen" in names
    assert "llm_cache" in names


def test_init_schema_is_idempotent(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    init_schema(memory_db)  # 두 번 실행해도 에러 없어야
    assert memory_db.execute("SELECT COUNT(*) FROM seen").fetchone()[0] == 0


def test_seen_primary_key_enforced(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    memory_db.execute(
        "INSERT INTO seen(source, ext_id, seen_at) VALUES ('dart', 'abc', '2026-04-22T06:00')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        memory_db.execute(
            "INSERT INTO seen(source, ext_id, seen_at) VALUES ('dart', 'abc', '2026-04-22T07:00')"
        )
