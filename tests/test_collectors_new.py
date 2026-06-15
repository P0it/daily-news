"""신규 수집기(13F·의회·FDA·와이어·애널)의 결정론적 헬퍼·파싱 테스트.

네트워크 호출 없이 점수·날짜 파싱·재구성 로직만 검증한다.
"""
from __future__ import annotations

from datetime import timezone

from news_briefing.collectors.analyst_ratings import _ACTION_SCORE, _parse_date, fetch_analyst_ratings
from news_briefing.collectors.congress_trades import _amount_score, _parse_tx_date
from news_briefing.collectors.fda_approvals import fetch_fda_approvals
from news_briefing.collectors.institutional_13f import fetch_institutional_13f
from news_briefing.collectors.press_wire import fetch_press_wires


# ── congress_trades ──────────────────────────────────────────────
def test_congress_parse_tx_date_us_format() -> None:
    d = _parse_tx_date("03/15/2026")
    assert d is not None
    assert (d.year, d.month, d.day) == (2026, 3, 15)
    assert d.tzinfo is timezone.utc


def test_congress_parse_tx_date_iso_format() -> None:
    d = _parse_tx_date("2026-03-15")
    assert d is not None and (d.year, d.month, d.day) == (2026, 3, 15)


def test_congress_parse_tx_date_invalid() -> None:
    assert _parse_tx_date("nonsense") is None


def test_congress_amount_score_tiers() -> None:
    assert _amount_score("$1,000,001 - $5,000,000") == 80
    assert _amount_score("$250,001 - $500,000") == 75
    assert _amount_score("$1,001 - $15,000") == 65


# ── analyst_ratings ──────────────────────────────────────────────
def test_analyst_action_score_map() -> None:
    assert _ACTION_SCORE["upgrade"] == (80, "positive")
    assert _ACTION_SCORE["downgrade"] == (78, "negative")


def test_analyst_parse_date_iso_z() -> None:
    d = _parse_date("2026-06-15T09:30:00.000Z")
    assert (d.year, d.month, d.day) == (2026, 6, 15)


def test_analyst_no_key_returns_empty() -> None:
    """키 없으면 네트워크 호출 없이 빈 결과."""
    assert fetch_analyst_ratings("") == []


# ── 네트워크 미설정/실패 시 빈 결과 (resilience) ────────────────────
def test_13f_no_user_agent_returns_empty() -> None:
    assert fetch_institutional_13f("") == []


def test_fda_returns_list_type(monkeypatch) -> None:
    """openFDA 호출 실패해도 list 반환(파이프라인 보호)."""
    import news_briefing.collectors.fda_approvals as mod

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(mod.requests, "get", _boom)
    assert fetch_fda_approvals() == []


def test_press_wire_returns_list_on_failure(monkeypatch) -> None:
    import news_briefing.collectors.press_wire as mod

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(mod.requests, "get", _boom)
    assert fetch_press_wires() == []
