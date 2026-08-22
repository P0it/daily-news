"""파일 정리·복원 로직 단위 테스트 (외부 의존성 없음)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from news_briefing.storage.briefings import export_briefings_to_local
from news_briefing.storage.cleanup import purge_files


def _write(path: Path, content: str = "{}") -> None:
    path.write_text(content, encoding="utf-8")


def test_purge_files_keeps_recent_days(tmp_path: Path) -> None:
    """cutoff 이내 파일은 남기고, 이전·형식 불량 파일만 지운다."""
    digests = tmp_path / "digests"
    briefings = tmp_path / "briefings"
    digests.mkdir()
    briefings.mkdir()

    today = date(2026, 6, 15)
    # 보관 대상 (오늘, 5일 전)
    _write(briefings / "2026-06-15.json")
    _write(briefings / "2026-06-10.json")
    _write(digests / "2026-06-15.txt", "x")
    # 삭제 대상 (보관 기간 초과)
    _write(briefings / "2026-05-01.json")
    _write(digests / "2026-05-01.txt", "x")
    # 삭제 대상 (날짜 형식 아님)
    _write(briefings / "garbage.json")

    counts = purge_files(digests, briefings, today, keep_days=7)

    assert (briefings / "2026-06-15.json").exists()
    assert (briefings / "2026-06-10.json").exists()
    assert not (briefings / "2026-05-01.json").exists()
    assert not (briefings / "garbage.json").exists()
    assert not (digests / "2026-05-01.txt").exists()
    assert counts["briefings"] == 2  # 2026-05-01 + garbage
    assert counts["digests"] == 1

    # index.json 은 남은 날짜를 최신순으로 담는다 (garbage 제외)
    index = json.loads((briefings / "index.json").read_text(encoding="utf-8"))
    assert index["dates"] == ["2026-06-15", "2026-06-10"]


class _FakeQuery:
    """Supabase 쿼리 빌더를 흉내내는 간단한 페이크."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n: int):
        self._rows = self._rows[:n]
        return self

    def execute(self):
        class _Resp:
            data = self._rows

        return _Resp()


class _FakeConn:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def table(self, _name: str) -> _FakeQuery:
        return _FakeQuery(list(self._rows))


def test_export_briefings_to_local_restores_files(tmp_path: Path) -> None:
    """DB 행을 로컬 JSON + index.json 으로 복원한다."""
    briefings = tmp_path / "briefings"
    rows = [
        {"date": "2026-06-15", "data": {"date": "2026-06-15", "tabs": {}}},
        {"date": "2026-06-10", "data": {"date": "2026-06-10", "tabs": {}}},
        {"date": "2026-06-09", "data": None},  # 잘못된 행은 건너뜀
    ]
    conn = _FakeConn(rows)

    dates = export_briefings_to_local(conn, briefings, keep_days=30)

    assert dates == ["2026-06-15", "2026-06-10"]
    assert (briefings / "2026-06-15.json").exists()
    assert (briefings / "2026-06-10.json").exists()
    assert not (briefings / "2026-06-09.json").exists()
    index = json.loads((briefings / "index.json").read_text(encoding="utf-8"))
    assert index["dates"] == ["2026-06-15", "2026-06-10"]
