"""브리핑 데이터 자동 정리.

매일 morning 파이프라인 시작 시 실행. 일회성 데이터는 보관 불필요.
- seen: 14일 이상 된 항목 삭제 (최근 2주만 중복 필터에 필요)
- llm_cache, embeddings, rag_queries: 전부 삭제
- data/digests/*.txt, frontend/public/briefings/*.json: 오늘 것만 유지
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

SEEN_KEEP_DAYS = 14


def purge_seen(conn: Connection) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_KEEP_DAYS)).isoformat()
    r = conn.table("seen").delete().lt("seen_at", cutoff).execute()
    return len(r.data)


def purge_transient_tables(conn: Connection) -> dict[str, int]:
    """llm_cache, embeddings, rag_queries 전체 삭제."""
    counts: dict[str, int] = {}
    epoch = "1970-01-01T00:00:00+00:00"
    # 테이블별 타임스탬프 컬럼명이 다름
    table_ts = {"llm_cache": "created_at", "embeddings": "indexed_at", "rag_queries": "created_at"}
    for table, ts_col in table_ts.items():
        r = conn.table(table).delete().gte(ts_col, epoch).execute()
        counts[table] = len(r.data)
    return counts


def purge_files(
    digests_dir: Path,
    briefings_dir: Path,
    today: date,
) -> dict[str, int]:
    """오늘 날짜 파일을 제외하고 모두 삭제. index.json 도 갱신."""
    today_str = today.strftime("%Y-%m-%d")
    counts: dict[str, int] = {"digests": 0, "briefings": 0}

    for path in digests_dir.glob("*.txt"):
        if path.stem != today_str:
            path.unlink(missing_ok=True)
            counts["digests"] += 1

    for path in briefings_dir.glob("*.json"):
        if path.name == "index.json":
            continue
        if path.stem != today_str:
            path.unlink(missing_ok=True)
            counts["briefings"] += 1

    index_path = briefings_dir / "index.json"
    today_file = briefings_dir / f"{today_str}.json"
    dates = [today_str] if today_file.exists() else []
    index_path.write_text(
        json.dumps({"dates": dates}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return counts


def run_cleanup(
    conn: Connection,
    *,
    digests_dir: Path,
    briefings_dir: Path,
    today: date | None = None,
) -> None:
    today = today or datetime.now(tz=timezone.utc).date()

    seen_deleted = purge_seen(conn)
    table_counts = purge_transient_tables(conn)
    file_counts = purge_files(digests_dir, briefings_dir, today)

    log.info(
        "cleanup done: seen -%d, cache -%d, embeddings -%d, rag_queries -%d, "
        "digests -%d, briefings -%d",
        seen_deleted,
        table_counts["llm_cache"],
        table_counts["embeddings"],
        table_counts["rag_queries"],
        file_counts["digests"],
        file_counts["briefings"],
    )
