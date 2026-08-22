"""pick_outcomes Supabase 저장·조회.

picks_history(실적 탭용 30일 실시간 수익률, 단일 JSON 블롭)와 달리 pick_outcomes 는
픽 1건 = 1행으로 영구 보관한다. 30일 후 폐기하지 않고, 촉매 유형별 적중률 집계
(재학습 데이터)의 원천이 된다. 행 단위 컬럼이라 PostgREST 필터·파이썬 집계가 쉽다.

테이블이 아직 없으면(스키마 미적용) 호출부가 예외를 잡아 morning 전체를 멈추지 않도록
얇게 위임만 한다.
"""

from __future__ import annotations

import logging
from typing import Any

from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

_TABLE = "pick_outcomes"


def upsert_outcomes(conn: Connection, rows: list[dict[str, Any]]) -> None:
    """전체 컬럼을 갖춘 스냅샷 행을 upsert(삽입/교체)한다.

    NOT NULL 컬럼(rec_date 등)을 모두 포함한 신규 스냅샷 전용. 부분 갱신은
    update_outcome 을 써야 한다 — upsert 는 내부적으로 INSERT 를 시도해
    빠진 NOT NULL 컬럼에서 실패하기 때문.
    """
    if not rows:
        return
    conn.table(_TABLE).upsert(rows).execute()


def update_outcome(conn: Connection, row_id: str, patch: dict[str, Any]) -> None:
    """기존 행의 일부 컬럼만 갱신(UPDATE)한다 — 백필 채점 패치용.

    update 는 순수 UPDATE 라 패치에 없는 컬럼은 건드리지 않아, NOT NULL 제약을
    건드리지 않는다(upsert 와 달리 INSERT 경로를 타지 않음).
    """
    if not patch:
        return
    conn.table(_TABLE).update(patch).eq("id", row_id).execute()


def fetch_existing_ids(conn: Connection, ids: list[str]) -> set[str]:
    """주어진 id 중 이미 원장에 있는 것을 반환 (신규 픽만 insert 하기 위함)."""
    if not ids:
        return set()
    resp = conn.table(_TABLE).select("id").in_("id", ids).execute()
    return {row["id"] for row in (resp.data or [])}


def fetch_pending(conn: Connection, since: str, limit: int = 2000) -> list[dict[str, Any]]:
    """아직 모든 채점 시점이 채워지지 않은(price_20d IS NULL) 행을 반환.

    Args:
        since: 이 날짜(YYYY-MM-DD) 이후 추천만 — 너무 오래된 픽 재시도 방지.
    """
    resp = (
        conn.table(_TABLE)
        .select("*")
        .is_("price_20d", "null")
        .gte("rec_date", since)
        .order("rec_date", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def fetch_all(
    conn: Connection, since: str | None = None, limit: int = 5000
) -> list[dict[str, Any]]:
    """집계용으로 원장 전체(또는 since 이후)를 반환."""
    q = conn.table(_TABLE).select("*")
    if since:
        q = q.gte("rec_date", since)
    resp = q.order("rec_date", desc=True).limit(limit).execute()
    return resp.data or []
