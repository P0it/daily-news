"""브리핑 데이터 자동 정리.

매일 morning 파이프라인 시작 시 실행. 일회성 데이터는 보관 불필요.
- seen: 14일 이상 된 항목 삭제 (최근 2주만 중복 필터에 필요)
- llm_cache, embeddings, rag_queries: 전부 삭제
- data/digests/*.txt, frontend/public/briefings/*.json: 최근 N일치만 유지
  (달력에서 과거 브리핑을 보려면 로컬 파일을 일정 기간 남겨야 함.
   보관 기간은 성과탭 picks_history(MAX_TRACK_DAYS=30)와 맞춘다.)
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

SEEN_KEEP_DAYS = 14
# 로컬 브리핑·디지스트 보관 일수. picks_history(MAX_TRACK_DAYS=30)와 동일하게 둬
# 달력과 성과탭이 보여주는 날짜 범위가 어긋나지 않도록 한다.
BRIEFINGS_KEEP_DAYS = 30


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
    keep_days: int = BRIEFINGS_KEEP_DAYS,
) -> dict[str, int]:
    """최근 keep_days 일치만 남기고 오래된 파일 삭제. index.json 도 갱신.

    파일명(YYYY-MM-DD)을 날짜로 파싱해 cutoff 이전이거나 형식이 맞지 않는
    파일을 지운다. index.json 은 남은 브리핑 날짜를 최신순으로 담는다.
    """
    cutoff = today - timedelta(days=keep_days)
    counts: dict[str, int] = {"digests": 0, "briefings": 0}

    def _stem_date(stem: str) -> date | None:
        try:
            return datetime.strptime(stem, "%Y-%m-%d").date()
        except ValueError:
            return None

    for path in digests_dir.glob("*.txt"):
        d = _stem_date(path.stem)
        if d is None or d < cutoff:
            path.unlink(missing_ok=True)
            counts["digests"] += 1

    kept_dates: list[str] = []
    for path in briefings_dir.glob("*.json"):
        if path.name == "index.json":
            continue
        d = _stem_date(path.stem)
        if d is None or d < cutoff:
            path.unlink(missing_ok=True)
            counts["briefings"] += 1
        else:
            kept_dates.append(path.stem)

    kept_dates.sort(reverse=True)
    index_path = briefings_dir / "index.json"
    index_path.write_text(
        json.dumps({"dates": kept_dates}, ensure_ascii=False, indent=2),
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
