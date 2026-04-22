"""중복 알림 방지 (seen 테이블 인터페이스)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def is_seen(conn: sqlite3.Connection, source: str, ext_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM seen WHERE source = ? AND ext_id = ?", (source, ext_id)
    ).fetchone()
    return row is not None


def mark_seen(conn: sqlite3.Connection, source: str, ext_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO seen(source, ext_id, seen_at) VALUES (?, ?, ?)",
        (source, ext_id, now),
    )
    conn.commit()


def filter_unseen(
    conn: sqlite3.Connection, items: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    return [(s, i) for s, i in items if not is_seen(conn, s, i)]
