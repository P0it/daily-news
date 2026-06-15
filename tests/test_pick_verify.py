"""pick_verify 검증 로직 테스트 (네트워크·LLM 호출 모킹)."""
from __future__ import annotations

import news_briefing.analysis.pick_verify as pv
from news_briefing.analysis.pick_verify import apply_verification, verify_ticker_exists


def _issues() -> list[dict]:
    return [
        {
            "asset": "AI 인프라",
            "signal": "전력 수요 급증",
            "picks": [
                {"ticker": "NVDA", "name": "Nvidia", "description": "GPU"},
                {"ticker": "FAKE", "name": "날조주", "description": "근거 없음"},
                {"ticker": "VRT", "name": "Vertiv", "description": "냉각"},
            ],
        }
    ]


def test_apply_verification_drops_and_flags(monkeypatch) -> None:
    # LLM 판정: NVDA keep, FAKE drop, VRT flag
    monkeypatch.setattr(
        pv, "verify_picks_llm", lambda issues, ev: {"NVDA": "keep", "FAKE": "drop", "VRT": "flag"}
    )
    # 티커 실존: 전부 존재한다고 가정
    monkeypatch.setattr(pv, "verify_ticker_exists", lambda t, s, conn=None: True)

    out = apply_verification(_issues(), scope="foreign", evidence_lines=[])
    tickers = [p["ticker"] for p in out[0]["picks"]]
    assert "FAKE" not in tickers  # drop 제거됨
    assert tickers == ["NVDA", "VRT"]
    statuses = {p["ticker"]: p["verifyStatus"] for p in out[0]["picks"]}
    assert statuses["NVDA"] == "ok"
    assert statuses["VRT"] == "review"  # flag → review


def test_ticker_unknown_becomes_review_not_dropped(monkeypatch) -> None:
    monkeypatch.setattr(pv, "verify_picks_llm", lambda issues, ev: {})  # 모두 keep
    # 실존 확인 실패(네트워크 등) — 그래도 drop 하지 않음
    monkeypatch.setattr(pv, "verify_ticker_exists", lambda t, s, conn=None: False)

    out = apply_verification(_issues(), scope="foreign", evidence_lines=[])
    assert len(out[0]["picks"]) == 3  # 아무것도 제거 안 됨
    assert all(p["verifyStatus"] == "review" for p in out[0]["picks"])


def test_llm_failure_keeps_all(monkeypatch) -> None:
    """LLM 검증이 빈 dict 면 모두 keep 으로 처리(파이프라인 보호)."""
    monkeypatch.setattr(pv, "verify_picks_llm", lambda issues, ev: {})
    monkeypatch.setattr(pv, "verify_ticker_exists", lambda t, s, conn=None: True)
    out = apply_verification(_issues(), scope="foreign", evidence_lines=[])
    assert len(out[0]["picks"]) == 3
    assert all(p["verifyStatus"] == "ok" for p in out[0]["picks"])


def test_domestic_ticker_format_rejected_without_db(monkeypatch) -> None:
    """6자리 아닌 국내 티커는 DB·yfinance 없이도 False."""
    monkeypatch.setattr(pv, "_yf_exists", lambda c: False)
    assert verify_ticker_exists("AAPL", "domestic", conn=None) is False
    assert verify_ticker_exists("", "foreign", conn=None) is False
