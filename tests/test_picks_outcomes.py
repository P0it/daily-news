"""pick_outcomes 적중 라벨링·추출·집계 단위 테스트 (외부 의존성 없음)."""

from __future__ import annotations

from news_briefing.analysis.picks_outcomes import (
    DEAD_BAND_PCT,
    calibration_report,
    extract_outcome_rows,
    label_hit,
    score_horizon,
)

# ── label_hit ────────────────────────────────────────────────────────────────


def test_positive_hit_when_up():
    assert label_hit("positive", 5.0) == 1


def test_positive_miss_when_down():
    assert label_hit("positive", -5.0) == 0


def test_negative_hit_when_down():
    assert label_hit("negative", -5.0) == 1


def test_negative_miss_when_up():
    assert label_hit("negative", 5.0) == 0


def test_mixed_always_none():
    # 모호 버킷: 방향성 베팅 아님 → 적중/실패 미판정
    assert label_hit("mixed", 10.0) is None
    assert label_hit("mixed", -10.0) is None


def test_deadband_is_unjudged():
    small = DEAD_BAND_PCT / 2
    assert label_hit("positive", small) is None
    assert label_hit("negative", -small) is None


def test_none_return_is_none():
    assert label_hit("positive", None) is None


# ── score_horizon (알파 계산·채점) ───────────────────────────────────────────


def test_alpha_hit_when_beats_market_up():
    # 주가 +10%, 지수 +4% → 알파 +6% → positive 적중
    s = score_horizon("positive", 100.0, 110.0, 100.0, 104.0)
    assert s["ret"] == 10.0
    assert s["bench_ret"] == 4.0
    assert s["alpha"] == 6.0
    assert s["hit"] == 1


def test_alpha_hit_when_falls_but_beats_market():
    # 핵심 케이스: 주가 -2% 로 빠졌지만 지수는 -5% → 알파 +3% → 촉매 작동(적중)
    s = score_horizon("positive", 100.0, 98.0, 100.0, 95.0)
    assert s["ret"] == -2.0
    assert s["alpha"] == 3.0
    assert s["hit"] == 1


def test_alpha_miss_when_rises_but_lags_market():
    # 주가 +1% 올랐어도 지수 +5% → 알파 -4% → 촉매 실패(시장에 묻어간 것)
    s = score_horizon("positive", 100.0, 101.0, 100.0, 105.0)
    assert s["alpha"] == -4.0
    assert s["hit"] == 0


def test_alpha_negative_direction_hit_when_underperforms():
    # 악재 예측: 지수보다 더 빠지면 적중. 주가 -10%, 지수 0% → 알파 -10% → hit
    s = score_horizon("negative", 100.0, 90.0, 100.0, 100.0)
    assert s["hit"] == 1


def test_no_benchmark_leaves_alpha_and_hit_none():
    # 벤치마크 없으면 절대수익만 남기고 적중은 보류(시장 탓/실력 구분 불가)
    s = score_horizon("positive", 100.0, 110.0, None, None)
    assert s["ret"] == 10.0
    assert s["alpha"] is None
    assert s["hit"] is None


def test_invalid_baseline_returns_none():
    assert score_horizon("positive", None, 110.0, 100.0, 104.0) is None
    assert score_horizon("positive", 0.0, 110.0, 100.0, 104.0) is None


# ── extract_outcome_rows ─────────────────────────────────────────────────────


def _briefing() -> dict:
    return {
        "date": "2026-06-19",
        "tabs": {
            "economy": {
                "hotIssues": {
                    "domestic": [
                        {
                            "asset": "조선",
                            "direction": "positive",
                            "signal": "공급계약",
                            "picks": [
                                {
                                    "ticker": "009540",
                                    "name": "HD한국조선해양",
                                    "description": "수주 모멘텀",
                                    "consensus_risk": "medium",
                                    "verifyStatus": "ok",
                                    "isFiler": True,
                                }
                            ],
                        }
                    ],
                    "foreign": [
                        {
                            "asset": "해운",
                            "direction": "mixed",
                            "signal": "M&A",
                            "picks": [
                                {
                                    "ticker": "SBLK",
                                    "name": "스타불크",
                                    "description": "업계 통합 수혜",
                                    "consensus_risk": "medium",
                                    "verifyStatus": "review",
                                    "isFiler": False,
                                },
                                {"ticker": "", "name": "빈 티커"},  # 무시되어야 함
                            ],
                        }
                    ],
                }
            }
        },
    }


def test_extract_basic_fields():
    rows = extract_outcome_rows(_briefing())
    assert len(rows) == 2  # 빈 티커 제외
    by_ticker = {r["ticker"]: r for r in rows}

    kr = by_ticker["009540"]
    assert kr["id"] == "2026-06-19-domestic-009540"
    assert kr["scope"] == "domestic"
    assert kr["currency"] == "KRW"
    assert kr["direction"] == "positive"
    assert kr["signal"] == "공급계약"
    assert kr["is_filer"] == 1
    assert kr["price_at_rec"] is None  # 스냅샷 시점엔 미채움

    us = by_ticker["SBLK"]
    assert us["id"] == "2026-06-19-foreign-SBLK"
    assert us["currency"] == "USD"
    assert us["verify_status"] == "review"
    assert us["is_filer"] == 0


def test_extract_empty_when_no_date():
    assert extract_outcome_rows({"tabs": {}}) == []


# ── calibration_report (store 를 가짜로 주입) ────────────────────────────────


class _FakeResp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_):
        return self

    def gte(self, *_):
        return self

    def order(self, *_, **__):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        return _FakeResp(self._rows)


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def table(self, *_):
        return _FakeQuery(self._rows)


def test_calibration_hit_rate_by_direction():
    rows = [
        # positive 3건: 2적중 1실패 → hit_rate 0.667
        {
            "direction": "positive",
            "scope": "domestic",
            "consensus_risk": "low",
            "verify_status": "ok",
            "signal": "공급계약",
            "hit_1d": 1,
            "ret_1d": 4.0,
            "hit_5d": 1,
            "ret_5d": 6.0,
            "hit_20d": 1,
            "ret_20d": 9.0,
        },
        {
            "direction": "positive",
            "scope": "domestic",
            "consensus_risk": "low",
            "verify_status": "ok",
            "signal": "공급계약",
            "hit_1d": 1,
            "ret_1d": 2.0,
            "hit_5d": 0,
            "ret_5d": -3.0,
            "hit_20d": 0,
            "ret_20d": -5.0,
        },
        {
            "direction": "positive",
            "scope": "foreign",
            "consensus_risk": "medium",
            "verify_status": "review",
            "signal": "M&A",
            "hit_1d": 0,
            "ret_1d": -2.0,
            "hit_5d": None,
            "ret_5d": None,
            "hit_20d": None,
            "ret_20d": None,
        },
    ]
    report = calibration_report(_FakeConn(rows))

    assert report["overall"]["n"] == 3
    pos = report["by_direction"]["positive"]
    assert pos["n"] == 3
    assert pos["1d"]["graded"] == 3
    assert pos["1d"]["hit_rate"] == round(2 / 3, 3)
    # 20d 는 2건만 채점됨
    assert pos["20d"]["graded"] == 2
    assert pos["20d"]["hit_rate"] == 0.5


def test_calibration_groups_present():
    rows = [
        {
            "direction": "mixed",
            "scope": "foreign",
            "consensus_risk": "high",
            "verify_status": "ok",
            "signal": "실적",
            "hit_1d": None,
            "ret_1d": 3.0,
            "hit_5d": None,
            "ret_5d": None,
            "hit_20d": None,
            "ret_20d": None,
        },
    ]
    report = calibration_report(_FakeConn(rows))
    assert "by_scope" in report
    assert "foreign" in report["by_scope"]
    assert "by_signal" in report
    # mixed 는 적중 미판정이지만 평균 수익률은 잡힌다
    assert report["by_direction"]["mixed"]["1d"]["avg_ret"] == 3.0
    assert report["by_direction"]["mixed"]["1d"]["hit_rate"] is None
