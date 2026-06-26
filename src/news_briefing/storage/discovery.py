"""발굴 스크린 스냅샷 Supabase 저장·복원.

picks_history 와 동일 패턴: 최신 스냅샷 전체를 단일 행(id='current')에 JSON 블롭으로
보관한다(DECISIONS #16 — Supabase 단일 원본). 배포 빌드가 이 행을 읽어 프론트가 쓰는
로컬 JSON(frontend/public/discovery.json)을 복원한다.

테이블(`discovery_screens`)이 아직 없으면 호출부가 예외를 잡아 screen 을 멈추지 않도록
얇게 위임만 한다.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

_ROW_ID = "current"


def upsert_discovery(conn: Connection, data: dict) -> None:
    """발굴 스냅샷 전체 JSON 을 단일 행으로 저장한다 (원본 보관소)."""
    conn.table("discovery_screens").upsert(
        {
            "id": _ROW_ID,
            "data": data,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    ).execute()


def export_discovery_to_local(conn: Connection, path: Path) -> bool:
    """Supabase 의 발굴 스냅샷을 로컬 JSON 으로 복원. 성공 여부 반환."""
    resp = conn.table("discovery_screens").select("data").eq("id", _ROW_ID).limit(1).execute()
    rows = resp.data or []
    if not rows:
        return False
    data = rows[0].get("data") or {}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def write_discovery_local(path: Path, data: dict) -> None:
    """스냅샷을 로컬 JSON 으로 바로 기록(생성 머신에서 즉시 미리보기용)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
