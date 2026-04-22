from __future__ import annotations

from datetime import datetime

from news_briefing.analysis.picks import select_picks
from news_briefing.collectors.base import CollectedItem


def _mk(
    company: str = "삼성전자",
    code: str = "005930",
    score: int = 80,
    source: str = "dart",
    ext_id: str = "x",
) -> tuple[CollectedItem, int, str]:
    it = CollectedItem(
        source=source,
        ext_id=ext_id,
        kind="disclosure",
        title="타이틀",
        url="https://x",
        published_at=datetime(2026, 4, 22),
        company=company,
        company_code=code,
    )
    return it, score, "positive"


def test_select_picks_splits_domestic_and_foreign() -> None:
    scored = [
        _mk(source="dart", code="005930", ext_id="1"),
        _mk(source="edgar", code="NVDA", ext_id="2", company="NVIDIA"),
    ]
    result = select_picks(scored, n_per_side=6)
    assert len(result.domestic) == 1
    assert len(result.foreign) == 1


def test_dedup_same_company_keeps_highest_score() -> None:
    scored = [
        _mk(code="005930", score=70, ext_id="a"),
        _mk(code="005930", score=90, ext_id="b"),
        _mk(code="005930", score=60, ext_id="c"),
    ]
    result = select_picks(scored, n_per_side=6)
    assert len(result.domestic) == 1
    assert result.domestic[0][1] == 90


def test_picks_sorted_desc_by_score() -> None:
    scored = [
        _mk(code="A", score=60, ext_id="a"),
        _mk(code="B", score=85, ext_id="b"),
        _mk(code="C", score=75, ext_id="c"),
    ]
    result = select_picks(scored, n_per_side=6)
    scores = [s for _, s, _ in result.domestic]
    assert scores == [85, 75, 60]


def test_picks_truncates_to_n_per_side() -> None:
    scored = [_mk(code=f"C{i}", score=100 - i, ext_id=str(i)) for i in range(10)]
    result = select_picks(scored, n_per_side=6)
    assert len(result.domestic) == 6
    assert [s for _, s, _ in result.domestic] == [100, 99, 98, 97, 96, 95]


def test_empty_input_returns_empty_picks() -> None:
    result = select_picks([], n_per_side=6)
    assert result.domestic == []
    assert result.foreign == []


def test_below_min_score_filtered() -> None:
    """Picks 도 기본 임계값(60) 미만은 제외."""
    scored = [
        _mk(code="A", score=80, ext_id="a"),
        _mk(code="B", score=45, ext_id="b"),
    ]
    result = select_picks(scored, n_per_side=6, min_score=60)
    codes = [it.company_code for it, _, _ in result.domestic]
    assert codes == ["A"]
