"""급상승 탐지 로직 단위 테스트 — 네트워크 의존 없음."""

from __future__ import annotations

from news_briefing.analysis.surge import Surge, attach_disclosures, find_surges
from news_briefing.collectors.krx_market import KrxDaily, parse_krx_rows


def _row(
    code: str,
    *,
    name: str = "테스트종목",
    value: int = 10_000_000_000,
    change_pct: float = 10.0,
    market_cap: int = 500_000_000_000,
    market: str = "KOSPI",
) -> KrxDaily:
    return KrxDaily(
        bas_dd="20260721",
        code=code,
        name=name,
        market=market,
        sector="",
        close=10_000.0,
        change=900.0,
        change_pct=change_pct,
        volume=1_000_000,
        value=value,
        market_cap=market_cap,
    )


def _series(today: list[KrxDaily], baseline_value: int = 1_000_000_000, days: int = 5):
    """today + 동일 종목들의 평탄한 baseline 거래일 `days` 개."""
    past = [
        [_row(r.code, name=r.name, value=baseline_value, market_cap=r.market_cap) for r in today]
        for _ in range(days)
    ]
    return [today, *past]


def test_거래대금_배수가_기준_미만이면_제외된다():
    # 당일 20억, 평균 10억 → 2배. 기본 임계 3배 미만
    today = [_row("000100", value=2_000_000_000)]
    assert find_surges(_series(today, baseline_value=1_000_000_000)) == []


def test_배수와_등락률을_모두_넘으면_선정된다():
    today = [_row("000100", value=10_000_000_000, change_pct=12.0)]
    out = find_surges(_series(today, baseline_value=1_000_000_000))
    assert len(out) == 1
    assert out[0].code == "000100"
    assert out[0].value_multiple == 10.0
    assert out[0].ticker == "000100.KS"


def test_등락률이_낮으면_거래대금이_터져도_제외된다():
    today = [_row("000100", value=50_000_000_000, change_pct=1.0)]
    assert find_surges(_series(today)) == []


def test_시총_거래대금_하한으로_잡주를_거른다():
    small_cap = _row("000100", market_cap=1_000_000_000)
    thin = _row("000200", value=100_000_000)
    assert find_surges(_series([small_cap, thin], baseline_value=10_000_000)) == []


def test_우선주와_스팩은_제외된다():
    today = [
        _row("00010K", name="삼성전자우"),  # 6자리 숫자 아님 → 수집 단계에서도 걸림
        _row("000105", name="현대차우"),
        _row("000205", name="교보10호스팩"),
    ]
    assert find_surges(_series(today)) == []


def test_신규상장처럼_baseline_없는_종목은_보류된다():
    today = [_row("000100"), _row("999999")]
    series = _series([_row("000100")], baseline_value=1_000_000_000)
    series[0] = today  # 999999 는 baseline 에 없음
    out = find_surges(series)
    assert [s.code for s in out] == ["000100"]


def test_baseline이_없으면_빈_결과():
    assert find_surges([[_row("000100")]]) == []
    assert find_surges([]) == []


def test_배수_내림차순_정렬과_top_n():
    today = [
        _row("000100", value=5_000_000_000),
        _row("000200", value=20_000_000_000),
        _row("000300", value=10_000_000_000),
    ]
    out = find_surges(_series(today, baseline_value=1_000_000_000), top_n=2)
    assert [s.code for s in out] == ["000200", "000300"]


class _Item:
    def __init__(self, code: str, title: str):
        self.company_code = code
        self.title = title


def test_공시_대조는_종목코드로_붙는다():
    s = Surge(
        code="000100",
        name="테스트",
        market="KOSPI",
        sector="",
        close=1.0,
        change_pct=10.0,
        value=1,
        avg_value=1,
        value_multiple=1.0,
        market_cap=1,
    )
    out = attach_disclosures([s], [_Item("000100", "단일판매·공급계약체결"), _Item("999", "x")])
    assert out[0].disclosures == ["단일판매·공급계약체결"]


def test_공시가_없으면_빈_리스트로_남는다():
    s = Surge("000100", "테스트", "KOSPI", "", 1.0, 10.0, 1, 1, 1.0, 1)
    assert attach_disclosures([s], [])[0].disclosures == []


def test_krx_응답_파싱_콤마와_결측치_처리():
    data = {
        "OutBlock_1": [
            {
                "BAS_DD": "20260721",
                "ISU_SRT_CD": "005930",
                "ISU_NM": "삼성전자",
                "MKT_NM": "KOSPI",
                "TDD_CLSPRC": "71,200",
                "CMPPREVDD_PRC": "-800",
                "FLUC_RT": "-1.11",
                "ACC_TRDVOL": "12,345,678",
                "ACC_TRDVAL": "880,000,000,000",
                "MKTCAP": "425,000,000,000,000",
            },
            {"ISU_SRT_CD": "0059K0", "ISU_NM": "비표준"},  # 6자리 숫자 아님 → 스킵
            {
                "ISU_SRT_CD": "000100",
                "ISU_NM": "결측",
                "TDD_CLSPRC": "-",
                "ACC_TRDVAL": "",
            },
        ]
    }
    rows = parse_krx_rows(data, "KOSPI")
    assert [r.code for r in rows] == ["005930", "000100"]
    assert rows[0].close == 71_200.0
    assert rows[0].change_pct == -1.11
    assert rows[0].value == 880_000_000_000
    assert rows[1].close == 0.0 and rows[1].value == 0
