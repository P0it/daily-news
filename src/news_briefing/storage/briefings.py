"""브리핑 JSON Supabase 저장 (briefings 테이블)."""
from __future__ import annotations

from datetime import UTC, datetime

from news_briefing.storage.db import Connection


def upsert_briefing(conn: Connection, date: str, data: dict) -> None:
    """오늘 브리핑 JSON 을 briefings 테이블에 저장. 프론트엔드가 직접 읽는다."""
    now = datetime.now(UTC).isoformat()
    conn.table("briefings").upsert({
        "date": date,
        "data": data,
        "created_at": now,
    }).execute()
