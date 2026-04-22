from __future__ import annotations

import sqlite3

from news_briefing.storage.cache import cache_get, cache_put, hash_content
from news_briefing.storage.db import init_schema


def test_hash_is_deterministic() -> None:
    assert hash_content("summarize", "hello") == hash_content("summarize", "hello")
    assert hash_content("summarize", "hello") != hash_content("summarize", "world")
    assert hash_content("summarize", "hello") != hash_content("glossary", "hello")


def test_cache_miss_returns_none(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert cache_get(memory_db, "summarize", "hello") is None


def test_cache_hit_returns_stored_output(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    cache_put(memory_db, "summarize", "hello", "안녕 세상", "claude-cli")
    assert cache_get(memory_db, "summarize", "hello") == "안녕 세상"


def test_cache_put_replaces_on_same_key(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    cache_put(memory_db, "summarize", "x", "A", "claude-cli")
    cache_put(memory_db, "summarize", "x", "B", "claude-cli")
    # 정책: 후자 우선 (재생성 케이스)
    assert cache_get(memory_db, "summarize", "x") == "B"
