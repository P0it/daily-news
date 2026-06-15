"""picks_history Supabase 저장·복원.

picks_history 는 전체가 하나의 문서({updatedAt, records[]})이므로 단일 행
(id='current')에 JSON 블롭으로 보관한다. 여러 생성 머신이 같은 행을 upsert 하고,
배포 빌드(또는 다른 머신)는 이 행에서 읽어 로컬 파일을 복원한다.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

_ROW_ID = "current"


def upsert_picks_history(conn: Connection, data: dict) -> None:
    """picks_history 전체 JSON 을 단일 행으로 저장한다 (원본 보관소)."""
    conn.table("picks_history").upsert(
        {
            "id": _ROW_ID,
            "data": data,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    ).execute()


def export_picks_history_to_local(conn: Connection, path: Path) -> int:
    """Supabase 의 picks_history 를 로컬 JSON 으로 복원. 레코드 수 반환."""
    resp = conn.table("picks_history").select("data").eq("id", _ROW_ID).limit(1).execute()
    rows = resp.data or []
    if not rows:
        return 0
    data = rows[0].get("data") or {"updatedAt": "", "records": []}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data.get("records", []))
