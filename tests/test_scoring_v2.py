from __future__ import annotations

from news_briefing.analysis.scoring import ScoringContext, score_with_context


def test_self_stock_buyback_scaled_by_amount() -> None:
    """자기주식취득 규모 보정 (SIGNALS.md 2.3 stacking).

    - 1% 이상: +10
    - 5% 이상: 추가 +15 (누적 최대 +25)
    """
    below = score_with_context(
        "자기주식취득결정",
        ScoringContext(amount=1_000_000_000, market_cap=1_000_000_000_000),  # 0.1%
    )
    mid = score_with_context(
        "자기주식취득결정",
        ScoringContext(amount=20_000_000_000, market_cap=1_000_000_000_000),  # 2%
    )
    heavy = score_with_context(
        "자기주식취득결정",
        ScoringContext(amount=60_000_000_000, market_cap=1_000_000_000_000),  # 6%
    )
    assert below.score == 80  # below 1% 문턱
    assert mid.score == 80 + 10  # 1~5%: +10 만
    # 5% 이상: +10 +15 stacking = +25 → 80+25 = 105, clamp 100
    assert heavy.score == 100


def test_self_stock_buyback_market_purchase_bonus() -> None:
    tr = score_with_context(
        "자기주식취득결정", ScoringContext(acquisition_method="신탁")
    )
    mkt = score_with_context(
        "자기주식취득결정", ScoringContext(acquisition_method="장내매수")
    )
    assert mkt.score == tr.score + 5


def test_insider_trade_buy_vs_sell_direction() -> None:
    buy = score_with_context(
        "임원ㆍ주요주주특정증권등소유상황보고서",
        ScoringContext(trade_type="매수", is_ceo=True, amount=2_000_000_000),
    )
    sell = score_with_context(
        "임원ㆍ주요주주특정증권등소유상황보고서",
        ScoringContext(trade_type="매도", stake_change_pct=2.0),
    )
    assert buy.direction == "positive"
    assert sell.direction == "negative"
    assert buy.score == 70 + 15 + 10  # CEO + 10억 초과
    assert sell.score == 70 + 15  # 지분율 1% 초과


def test_empty_context_matches_v1_behavior() -> None:
    r = score_with_context("자기주식취득결정", ScoringContext())
    assert r.score == 80
    assert r.direction == "positive"


def test_scoring_result_clamps_at_100() -> None:
    r = score_with_context(
        "자기주식취득결정",
        ScoringContext(
            amount=500_000_000_000,
            market_cap=1_000_000_000_000,
            acquisition_method="장내매수",
        ),
    )
    assert r.score <= 100
