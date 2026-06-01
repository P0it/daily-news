"""중복 알림 방지 (seen 테이블 인터페이스)."""
from __future__ import annotations

from datetime import UTC, datetime

from news_briefing.storage.db import Connection


def is_seen(conn: Connection, source: str, ext_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM seen WHERE source = %s AND ext_id = %s", (source, ext_id)
    ).fetchone()
    return row is not None


def mark_seen(conn: Connection, source: str, ext_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO seen(source, ext_id, seen_at) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING",
        (source, ext_id, now),
    )
    conn.commit()


def filter_unseen(
    conn: Connection, items: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    return [(s, i) for s, i in items if not is_seen(conn, s, i)]
