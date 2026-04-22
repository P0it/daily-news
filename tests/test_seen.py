from __future__ import annotations

import sqlite3

from news_briefing.storage.db import init_schema
from news_briefing.storage.seen import filter_unseen, is_seen, mark_seen


def test_mark_and_is_seen(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert not is_seen(memory_db, "dart", "abc")
    mark_seen(memory_db, "dart", "abc")
    assert is_seen(memory_db, "dart", "abc")


def test_mark_seen_is_idempotent(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    mark_seen(memory_db, "rss:hankyung", "guid-1")
    mark_seen(memory_db, "rss:hankyung", "guid-1")  # no IntegrityError
    rows = memory_db.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
    assert rows == 1


def test_filter_unseen_preserves_order(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    mark_seen(memory_db, "dart", "b")
    items = [("dart", "a"), ("dart", "b"), ("dart", "c")]
    result = filter_unseen(memory_db, items)
    assert result == [("dart", "a"), ("dart", "c")]
