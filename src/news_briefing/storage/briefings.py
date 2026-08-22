"""브리핑 JSON Supabase 저장 (briefings 테이블)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)


def upsert_briefing(conn: Connection, date: str, data: dict) -> None:
    """오늘 브리핑 JSON 을 briefings 테이블에 저장한다 (원본 보관소)."""
    now = datetime.now(UTC).isoformat()
    conn.table("briefings").upsert(
        {
            "date": date,
            "data": data,
            "created_at": now,
        }
    ).execute()


def export_briefings_to_local(
    conn: Connection,
    briefings_dir: Path,
    *,
    keep_days: int = 90,
) -> list[str]:
    """Supabase briefings 테이블의 최근 keep_days 일치를 로컬 정적 파일로 내보낸다.

    프론트엔드(정적 호스팅)는 frontend/public/briefings/*.json 만 읽으므로,
    cleanup으로 지워진 과거 브리핑을 DB(원본)에서 복원해 달력에서 다시 볼 수 있게
    한다. index.json 도 내보낸 날짜로 갱신한다.

    기본값은 cleanup.BRIEFINGS_KEEP_DAYS(90)와 같게 둔다. 성과탭
    (picks_history, MAX_TRACK_DAYS=30)과는 일부러 다르다 — 성과 추적과 달력
    열람은 목적이 다르다. 배포 사이트의 달력 범위는 결국
    frontend/scripts/export-from-supabase.mjs 의 KEEP_DAYS 가 정하므로
    셋을 함께 봐야 한다.

    Returns:
        내보낸 날짜 목록 (최신순).
    """
    briefings_dir.mkdir(parents=True, exist_ok=True)
    resp = (
        conn.table("briefings")
        .select("date, data")
        .order("date", desc=True)
        .limit(keep_days)
        .execute()
    )
    dates: list[str] = []
    for row in resp.data or []:
        date_str = row.get("date")
        data = row.get("data")
        if not date_str or not isinstance(data, dict):
            continue
        (briefings_dir / f"{date_str}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        dates.append(date_str)

    dates.sort(reverse=True)
    (briefings_dir / "index.json").write_text(
        json.dumps({"dates": dates}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("브리핑 로컬 복원: %d일치 (%s)", len(dates), dates[:1])
    return dates
