"""pick_verify 검증 로직 테스트 (네트워크·LLM 호출 모킹)."""

from __future__ import annotations

import news_briefing.analysis.pick_verify as pv
from news_briefing.analysis.pick_verify import apply_verification, verify_ticker_format


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


def _ground(grounded: bool = True, filer=None, evidence=None) -> dict:
    return {"grounded": grounded, "filer": filer, "evidence": evidence}


def test_apply_verification_drops_and_flags(monkeypatch) -> None:
    # 촉매는 grounded, 픽 판정: NVDA keep, FAKE drop, VRT flag(+사유)
    monkeypatch.setattr(
        pv,
        "verify_issues_llm",
        lambda issues, ev: (
            {0: _ground(True, filer="Nvidia")},
            {
                (0, "NVDA"): {"verdict": "keep", "reason": "", "is_filer": True},
                (0, "FAKE"): {"verdict": "drop", "reason": "근거 없음", "is_filer": False},
                (0, "VRT"): {
                    "verdict": "flag",
                    "reason": "연결고리가 간접적이에요",
                    "is_filer": False,
                },
            },
        ),
    )
    # 실존 확인은 네트워크 — 모킹
    monkeypatch.setattr(pv, "confirm_ticker_exists", lambda t, s, conn=None, fmp_api_key="": True)

    out = apply_verification(_issues(), scope="foreign", evidence_lines=[])
    tickers = [p["ticker"] for p in out[0]["picks"]]
    assert "FAKE" not in tickers  # drop 제거됨
    assert tickers == ["NVDA", "VRT"]
    by = {p["ticker"]: p for p in out[0]["picks"]}
    assert by["NVDA"]["verifyStatus"] == "ok"
    assert by["NVDA"]["isFiler"] is True
    assert by["VRT"]["verifyStatus"] == "review"  # flag → review
    assert by["VRT"]["verifyNote"] == "연결고리가 간접적이에요"  # 사유 노출


def test_fabricated_catalyst_drops_whole_issue(monkeypatch) -> None:
    """촉매(signal)가 근거에 없으면(grounded=false) 이슈 전체를 버린다.

    비에이치 환각 사례: '최대주주 변경' 공시가 실재하지 않음 → 이슈째 제거.
    """
    issues = [
        {
            "asset": "폴더블 부품",
            "signal": "최대주주 변경",
            "picks": [{"ticker": "090460", "name": "비에이치", "description": "FPCB 공급사"}],
        },
        {
            "asset": "반도체 소재",
            "signal": "전환사채 발행",
            "picks": [{"ticker": "357780", "name": "솔브레인", "description": "식각액"}],
        },
    ]
    monkeypatch.setattr(
        pv,
        "verify_issues_llm",
        lambda iss, ev: (
            {0: _ground(False), 1: _ground(True, filer="솔브레인홀딩스")},
            {(1, "357780"): {"verdict": "keep", "reason": "", "is_filer": False}},
        ),
    )
    monkeypatch.setattr(pv, "confirm_ticker_exists", lambda t, s, conn=None, fmp_api_key="": True)
    out = apply_verification(issues, scope="domestic", evidence_lines=[])
    assert len(out) == 1  # 환각 촉매 이슈 제거됨
    assert out[0]["asset"] == "반도체 소재"


def test_unconfirmed_ticker_stays_ok_not_review(monkeypatch) -> None:
    """실존 미확인이어도 형식이 정상이면 review 가 아니라 ok (정상 종목 오탐 방지)."""
    monkeypatch.setattr(pv, "verify_issues_llm", lambda issues, ev: ({}, {}))  # 모두 keep
    monkeypatch.setattr(pv, "confirm_ticker_exists", lambda t, s, conn=None, fmp_api_key="": False)

    out = apply_verification(_issues(), scope="foreign", evidence_lines=[])
    assert len(out[0]["picks"]) == 3  # 아무것도 제거 안 됨
    assert all(p["verifyStatus"] == "ok" for p in out[0]["picks"])
    assert all(p["tickerConfirmed"] is False for p in out[0]["picks"])


def test_malformed_domestic_ticker_flagged(monkeypatch) -> None:
    """국내 픽인데 6자리 코드가 아니면 review."""
    monkeypatch.setattr(pv, "verify_issues_llm", lambda issues, ev: ({}, {}))
    monkeypatch.setattr(pv, "confirm_ticker_exists", lambda t, s, conn=None, fmp_api_key="": True)
    issues = [{"asset": "테마", "signal": "x", "picks": [{"ticker": "AAPL", "name": "잘못"}]}]
    out = apply_verification(issues, scope="domestic", evidence_lines=[])
    assert out[0]["picks"][0]["verifyStatus"] == "review"
    assert out[0]["picks"][0]["verifyNote"]  # 형식 오류 사유 채워짐


def test_llm_failure_keeps_all(monkeypatch) -> None:
    """LLM 검증이 빈 결과면 모두 keep + ok (fail-open, 파이프라인 보호)."""
    monkeypatch.setattr(pv, "verify_issues_llm", lambda issues, ev: ({}, {}))
    monkeypatch.setattr(pv, "confirm_ticker_exists", lambda t, s, conn=None, fmp_api_key="": True)
    out = apply_verification(_issues(), scope="foreign", evidence_lines=[])
    assert len(out) == 1  # 판정 없으면 이슈 유지(fail-open)
    assert len(out[0]["picks"]) == 3
    assert all(p["verifyStatus"] == "ok" for p in out[0]["picks"])


def test_verify_ticker_format() -> None:
    assert verify_ticker_format("AAPL", "foreign") == "ok"
    assert verify_ticker_format("", "foreign") == "malformed"
    assert verify_ticker_format("005930", "domestic") == "ok"
    assert verify_ticker_format("AAPL", "domestic") == "malformed"  # 국내 비6자리
