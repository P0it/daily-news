"""발굴 픽 성과 원장(discovery_outcomes) Supabase 저장·조회.

pick_outcomes 스토리지와 동일 패턴(행 단위 upsert/update). 테이블 미적용 시 호출부가
예외를 잡아 screen 을 멈추지 않도록 얇게 위임만 한다.
"""

from __future__ import annotations

import logging
from typing import Any

from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

_TABLE = "discovery_outcomes"


def upsert_outcomes(conn: Connection, rows: list[dict[str, Any]]) -> None:
    """전체 컬럼을 갖춘 신규 스냅샷 행을 upsert 한다."""
    if not rows:
        return
    conn.table(_TABLE).upsert(rows).execute()


def update_outcome(conn: Connection, row_id: str, patch: dict[str, Any]) -> None:
    """기존 행의 일부 컬럼만 갱신(채점 백필 패치용)."""
    if not patch:
        return
    conn.table(_TABLE).update(patch).eq("id", row_id).execute()


def fetch_existing_ids(conn: Connection, ids: list[str]) -> set[str]:
    """주어진 id 중 이미 원장에 있는 것을 반환(신규만 insert)."""
    if not ids:
        return set()
    resp = conn.table(_TABLE).select("id").in_("id", ids).execute()
    return {row["id"] for row in (resp.data or [])}


def fetch_pending(conn: Connection, since: str, limit: int = 2000) -> list[dict[str, Any]]:
    """아직 마지막 채점 시점(price_60d)이 비어있는 행을 반환."""
    resp = (
        conn.table(_TABLE)
        .select("*")
        .is_("price_60d", "null")
        .gte("rec_date", since)
        .order("rec_date", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def fetch_all(conn: Connection, since: str | None = None) -> list[dict[str, Any]]:
    """집계 리포트용 — (선택) since 이후 전체 행."""
    q = conn.table(_TABLE).select("*")
    if since:
        q = q.gte("rec_date", since)
    return q.order("rec_date", desc=True).limit(5000).execute().data or []
