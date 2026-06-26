"""발굴 스크리너 단위 테스트 — 백분위·합성점수·정크필터 결정론 검증.

외부 의존 없이 합성 Fundamentals 입력만으로 랭킹·제외 규칙을 확인한다.
"""

from __future__ import annotations

from news_briefing.analysis.screener import (
    _is_junk,
    _metric_map,
    _percentile,
    screen,
)
from news_briefing.collectors.fundamentals import Fundamentals


def _fund(ticker: str, **kw: float | None) -> Fundamentals:
    """결측을 None 으로 채운 Fundamentals 빌더."""
    base: dict[str, object] = dict(
        ticker=ticker,
        scope="us",
        name=ticker,
        sector="Tech",
        currency="USD",
        market_cap=1e9,
        trailing_pe=None,
        forward_pe=None,
        price_to_book=None,
        peg=None,
        ev_to_ebitda=None,
        roe=None,
        profit_margin=None,
        operating_margin=None,
        debt_to_equity=None,
        revenue_growth=None,
        earnings_growth=None,
        free_cashflow=None,
    )
    base.update(kw)
    return Fundamentals(**base)  # type: ignore[arg-type]


# ── 백분위 ────────────────────────────────────────────────────────────────────


def test_percentile_midrank_handles_ties() -> None:
    vals = sorted([10.0, 20.0, 20.0, 40.0])
    # 10: less=0 eq=1 → 0.5/4 = 0.125
    assert _percentile(vals, 10.0) == 0.125
    # 20: less=1 eq=2 → (1+1)/4 = 0.5
    assert _percentile(vals, 20.0) == 0.5
    # 40: less=3 eq=1 → 3.5/4 = 0.875
    assert _percentile(vals, 40.0) == 0.875


# ── 정크 필터 ─────────────────────────────────────────────────────────────────


def test_junk_overlevered_excluded() -> None:
    m = _metric_map(
        _fund(
            "X",
            debt_to_equity=500.0,
            roe=0.2,
            profit_margin=0.1,
            trailing_pe=10.0,
            revenue_growth=0.1,
        )
    )
    assert _is_junk(m) is True


def test_junk_lossmaker_without_growth_excluded() -> None:
    m = _metric_map(
        _fund(
            "X",
            profit_margin=-0.3,
            revenue_growth=0.05,
            earnings_growth=-0.1,
            trailing_pe=None,
            roe=-0.1,
        )
    )
    assert _is_junk(m) is True


def test_lossmaker_with_strong_growth_kept() -> None:
    # 적자라도 매출 30% 성장이면 발굴 후보로 유지
    m = _metric_map(
        _fund(
            "X",
            profit_margin=-0.1,
            revenue_growth=0.30,
            operating_margin=-0.05,
            price_to_book=3.0,
            forward_pe=40.0,
        )
    )
    assert _is_junk(m) is False


def test_junk_data_poor_excluded() -> None:
    # 가용 지표 < 4 → 평가 불가로 제외
    m = _metric_map(_fund("X", trailing_pe=10.0, roe=0.2))
    assert _is_junk(m) is True


# ── 합성 랭킹 ─────────────────────────────────────────────────────────────────


def _rich(ticker: str, **kw: float | None) -> Fundamentals:
    """모든 핵심 지표가 채워진 종목(데이터 부족 제외 회피)."""
    base = dict(
        trailing_pe=15.0,
        forward_pe=14.0,
        price_to_book=2.0,
        peg=1.0,
        ev_to_ebitda=10.0,
        roe=0.15,
        profit_margin=0.12,
        operating_margin=0.15,
        debt_to_equity=80.0,
        revenue_growth=0.10,
        earnings_growth=0.12,
        free_cashflow=5e7,
    )
    base.update(kw)
    return _fund(ticker, **base)


def test_cheap_quality_growth_outranks_expensive_weak() -> None:
    universe = [
        # GOOD: 싸고(PE 8, PB 1) 우량(ROE 30%, 마진 25%) 고성장(매출 30%)
        _rich(
            "GOOD",
            trailing_pe=8.0,
            forward_pe=7.0,
            price_to_book=1.0,
            peg=0.5,
            ev_to_ebitda=5.0,
            roe=0.30,
            profit_margin=0.25,
            operating_margin=0.30,
            debt_to_equity=20.0,
            revenue_growth=0.30,
            earnings_growth=0.35,
        ),
        # MID: 평범
        _rich("MID"),
        # BAD: 비싸고(PE 60, PB 12) 저수익(ROE 3%) 저성장(2%)
        _rich(
            "BAD",
            trailing_pe=60.0,
            forward_pe=55.0,
            price_to_book=12.0,
            peg=4.0,
            ev_to_ebitda=40.0,
            roe=0.03,
            profit_margin=0.02,
            operating_margin=0.03,
            debt_to_equity=200.0,
            revenue_growth=0.02,
            earnings_growth=0.01,
        ),
    ]
    out = screen(universe, top_n=10)
    tickers = [r.ticker for r in out]
    assert tickers[0] == "GOOD"
    assert tickers[-1] == "BAD"
    good = next(r for r in out if r.ticker == "GOOD")
    bad = next(r for r in out if r.ticker == "BAD")
    # GOOD 이 모든 팩터에서 BAD 보다 우위
    assert good.value_score is not None and bad.value_score is not None
    assert good.value_score > bad.value_score
    assert good.quality_score is not None and good.quality_score >= 75
    assert "저평가" in good.highlights


def test_composite_uses_available_factors_when_growth_missing() -> None:
    # 성장 지표가 전부 없어도 가치·퀄리티만으로 합성(재정규화)되어 결과에 포함
    universe = [
        _rich("A", revenue_growth=None, earnings_growth=None),
        _rich("B"),
    ]
    out = screen(universe, top_n=10)
    a = next((r for r in out if r.ticker == "A"), None)
    assert a is not None
    assert a.growth_score is None
    assert 0 <= a.composite <= 100


def test_top_n_limits_output() -> None:
    universe = [_rich(f"T{i}", trailing_pe=10.0 + i) for i in range(30)]
    out = screen(universe, top_n=5)
    assert len(out) == 5
    # 점수 내림차순 정렬 보장
    assert all(out[i].composite >= out[i + 1].composite for i in range(len(out) - 1))


def test_empty_universe_returns_empty() -> None:
    assert screen([], top_n=5) == []
