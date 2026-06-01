"""중복 알림 방지 (seen 테이블 인터페이스)."""
from __future__ import annotations

from datetime import UTC, datetime

from news_briefing.storage.db import Connection


def is_seen(conn: Connection, source: str, ext_id: str) -> bool:
    r = (
        conn.table("seen")
        .select("source")
        .eq("source", source)
        .eq("ext_id", ext_id)
        .limit(1)
        .execute()
    )
    return len(r.data) > 0


def mark_seen(conn: Connection, source: str, ext_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    conn.table("seen").upsert({"source": source, "ext_id": ext_id, "seen_at": now}).execute()


def filter_unseen(
    conn: Connection, items: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    return [(s, i) for s, i in items if not is_seen(conn, s, i)]


def batch_filter_unseen(
    conn: Connection, items: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """source별로 묶어서 한 번에 조회 — N*2 요청을 source_count*1 요청으로 줄임."""
    if not items:
        return []
    from collections import defaultdict
    by_source: dict[str, list[str]] = defaultdict(list)
    for source, ext_id in items:
        by_source[source].append(ext_id)

    seen_pairs: set[tuple[str, str]] = set()
    chunk_size = 50  # URL 길이 제한 방지
    for source, ext_ids in by_source.items():
        for i in range(0, len(ext_ids), chunk_size):
            chunk = ext_ids[i : i + chunk_size]
            r = (
                conn.table("seen")
                .select("ext_id")
                .eq("source", source)
                .in_("ext_id", chunk)
                .execute()
            )
            for d in r.data:
                seen_pairs.add((source, d["ext_id"]))

    return [(s, i) for s, i in items if (s, i) not in seen_pairs]


def batch_mark_seen(conn: Connection, items: list[tuple[str, str]]) -> None:
    """여러 (source, ext_id) 를 upsert 로 저장. 청크 단위로 분할."""
    if not items:
        return
    now = datetime.now(UTC).isoformat()
    chunk_size = 100
    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]
        rows = [{"source": s, "ext_id": e, "seen_at": now} for s, e in chunk]
        conn.table("seen").upsert(rows).execute()
