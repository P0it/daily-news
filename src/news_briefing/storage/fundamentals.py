"""펀더멘털 스냅샷 Supabase 캐시 저장·조회.

발굴 스크린은 수백 종목의 yfinance `.info` 를 긁어 느리다(수 분). 재무는 분기 단위로
변하므로, 한 번 받은 스냅샷을 며칠간 재사용한다. ticker 1건 = 1행.

테이블(`fundamentals`)이 아직 없으면(스키마 미적용) 호출부가 예외를 잡아 스크린을
멈추지 않도록 얇게 위임만 한다(picks_outcomes 스토리지와 동일 방침).
"""

from __future__ import annotations

import logging
from typing import Any

from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

_TABLE = "fundamentals"


def upsert_fundamentals(conn: Connection, rows: list[dict[str, Any]]) -> None:
    """펀더멘털 스냅샷 행들을 upsert(삽입/교체). 각 행은 fetched_at 포함."""
    if not rows:
        return
    conn.table(_TABLE).upsert(rows).execute()


def fetch_recent(conn: Connection, since: str) -> dict[str, dict[str, Any]]:
    """fetched_at >= since 인 신선한 행을 ticker → row dict 로 반환.

    Args:
        since: ISO8601 문자열. 이 시각 이후 갱신된 스냅샷만 신선한 것으로 본다.
    """
    resp = conn.table(_TABLE).select("*").gte("fetched_at", since).execute()
    return {row["ticker"]: row for row in (resp.data or [])}
