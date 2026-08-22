from __future__ import annotations

from datetime import datetime

from news_briefing.analysis.watchlist import select_watchlist
from news_briefing.collectors.base import CollectedItem


def _mk(
    company: str = "삼성전자",
    code: str = "005930",
    score: int = 80,
    source: str = "dart",
    ext_id: str = "x",
    title: str = "단일판매ㆍ공급계약체결",
    direction: str = "positive",
    extra: dict | None = None,
) -> tuple[CollectedItem, int, str]:
    it = CollectedItem(
        source=source,
        ext_id=ext_id,
        kind="disclosure",
        title=title,
        url="https://x",
        published_at=datetime(2026, 6, 23),
        company=company,
        company_code=code,
        extra=extra or {},
    )
    return it, score, direction


def test_domestic_only_excludes_foreign() -> None:
    scored = [
        _mk(source="dart", code="005930", ext_id="1"),
        _mk(source="edgar", code="NVDA", ext_id="2", company="NVIDIA"),
    ]
    out = select_watchlist(scored, foreign=False)
    assert [w["code"] for w in out] == ["005930"]


def test_foreign_only_excludes_domestic() -> None:
    scored = [
        _mk(source="dart", code="005930", ext_id="1"),
        _mk(source="edgar", code="NVDA", ext_id="2", company="NVIDIA"),
    ]
    out = select_watchlist(scored, foreign=True)
    assert [w["code"] for w in out] == ["NVDA"]


def test_below_min_score_filtered() -> None:
    scored = [
        _mk(code="A", score=80, ext_id="a"),
        _mk(code="B", score=70, ext_id="b"),  # 75 미만 → 제외
    ]
    out = select_watchlist(scored, foreign=False, min_score=75)
    assert [w["code"] for w in out] == ["A"]


def test_dedup_same_company_keeps_highest() -> None:
    scored = [
        _mk(code="005930", score=78, ext_id="a"),
        _mk(code="005930", score=92, ext_id="b"),
    ]
    out = select_watchlist(scored, foreign=False)
    assert len(out) == 1
    assert out[0]["score"] == 92


def test_sorted_desc_and_truncated() -> None:
    scored = [_mk(code=f"C{i}", score=100 - i, ext_id=str(i)) for i in range(10)]
    out = select_watchlist(scored, foreign=False, n=6)
    assert [w["score"] for w in out] == [100, 99, 98, 97, 96, 95]


def test_exclude_keys_skips_picked_companies() -> None:
    scored = [
        _mk(code="005930", score=90, ext_id="a"),
        _mk(code="000660", score=85, ext_id="b", company="SK하이닉스"),
    ]
    out = select_watchlist(scored, foreign=False, exclude_keys={"005930"})
    assert [w["code"] for w in out] == ["000660"]


def test_dedup_same_title_when_company_empty() -> None:
    """와이어 항목은 회사명이 비어 같은 헤드라인이 중복 노출되던 문제 방지."""
    fx = {"scope": "foreign"}
    scored = [
        _mk(company="", code="", source="wire:prn", ext_id="a", title="AbbVie EC 승인", extra=fx),
        _mk(company="", code="", source="wire:prn", ext_id="b", title="AbbVie EC 승인", extra=fx),
    ]
    out = select_watchlist(scored, foreign=True)
    assert len(out) == 1


def test_item_shape() -> None:
    out = select_watchlist([_mk()], foreign=False)
    item = out[0]
    assert set(item) == {"company", "code", "title", "score", "direction", "source", "url"}
    assert item["direction"] == "positive"
