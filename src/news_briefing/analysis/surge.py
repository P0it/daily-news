"""급상승 종목 탐지 — KRX 일별매매정보 기반.

거래대금 급증은 그 자체로 촉매가 아니라 **촉매에 대한 시장의 반응**이다. 그래서
picks 스코어링에는 관여시키지 않고(DECISIONS #17 과 같은 이유: 이미 벌어진 일은
알파가 없다) 독립 조회 기능으로 둔다. 용도는 "어제 무슨 일이 있었나"를 되짚는 것.

판정은 등락률만 보지 않는다. 등락률은 품절주·저유동성 종목에서 쉽게 튀므로,
**직전 거래일들의 평균 거래대금 대비 배수**를 같이 요구해 실제로 돈이 몰린
종목만 남긴다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from news_briefing.collectors.krx_market import KrxDaily

log = logging.getLogger(__name__)

# 잡주 필터 기본값 — 약한 신호를 애초에 들이지 않는다
MIN_VALUE = 3_000_000_000  # 당일 거래대금 30억 미만 제외
MIN_MARKET_CAP = 30_000_000_000  # 시총 300억 미만 제외
MIN_CHANGE_PCT = 5.0  # 등락률 +5% 미만 제외
MIN_MULTIPLE = 3.0  # 평균 거래대금 대비 3배 미만 제외

# 보통주가 아닌 종목을 이름으로 걸러낸다 (우선주·스팩·리츠·ETN 잔여물)
_EXCLUDE_TOKENS = ("스팩", "리츠", "우B", "우C", "(전환)")


def _is_common_stock(name: str) -> bool:
    if any(tok in name for tok in _EXCLUDE_TOKENS):
        return False
    # '삼성전자우' 처럼 끝이 '우' 로 끝나면 우선주 (단, '삼성화재해상보험' 류 오탐 없음)
    return not name.endswith("우")


@dataclass(frozen=True, slots=True)
class Surge:
    """급상승 판정을 통과한 종목 한 건."""

    code: str
    name: str
    market: str
    sector: str
    close: float
    change_pct: float
    value: int  # 당일 거래대금 (원)
    avg_value: int  # 직전 거래일 평균 거래대금 (원)
    value_multiple: float  # value / avg_value
    market_cap: int
    disclosures: list[str] = field(default_factory=list)  # 같은 날 DART 공시 제목

    @property
    def ticker(self) -> str:
        """TradingView·야후 심볼용 접미사 포함 티커."""
        return f"{self.code}.{'KS' if self.market.startswith('KOSPI') else 'KQ'}"


def find_surges(
    series: list[list[KrxDaily]],
    *,
    min_value: int = MIN_VALUE,
    min_market_cap: int = MIN_MARKET_CAP,
    min_change_pct: float = MIN_CHANGE_PCT,
    min_multiple: float = MIN_MULTIPLE,
    top_n: int = 20,
) -> list[Surge]:
    """거래일 시계열(최신순)에서 급상승 종목을 골라 거래대금 배수 내림차순으로 반환한다.

    `series[0]` 이 판정 대상일이고 `series[1:]` 이 baseline 이다. baseline 이 비면
    배수를 계산할 수 없으므로 빈 리스트를 돌려준다.
    """
    if not series:
        return []
    if len(series) < 2:
        log.warning("baseline 거래일이 없어 급등 판정 불가 (거래일 %d개)", len(series))
        return []

    today, baseline = series[0], series[1:]

    # 종목별 과거 거래대금 누적 — 상장 직후 종목은 baseline 이 짧을 수 있다
    hist: dict[str, list[int]] = {}
    for day in baseline:
        for row in day:
            hist.setdefault(row.code, []).append(row.value)

    out: list[Surge] = []
    for row in today:
        if row.value < min_value or row.market_cap < min_market_cap:
            continue
        if row.change_pct < min_change_pct:
            continue
        if not _is_common_stock(row.name):
            continue
        past = hist.get(row.code) or []
        if not past:
            continue  # 신규 상장 등 비교 대상 없음 — 급등 판정 보류
        avg = sum(past) / len(past)
        if avg <= 0:
            continue
        multiple = row.value / avg
        if multiple < min_multiple:
            continue
        out.append(
            Surge(
                code=row.code,
                name=row.name,
                market=row.market,
                sector=row.sector,
                close=row.close,
                change_pct=row.change_pct,
                value=row.value,
                avg_value=int(avg),
                value_multiple=round(multiple, 2),
                market_cap=row.market_cap,
            )
        )

    out.sort(key=lambda s: s.value_multiple, reverse=True)
    return out[:top_n]


def attach_disclosures(surges: list[Surge], disclosures: list) -> list[Surge]:
    """급등 종목에 같은 기간 DART 공시 제목을 붙인다.

    "왜 올랐나"를 사람이 바로 판단할 수 있게 하는 용도다. 공시가 없으면 빈 리스트로
    남고, 그건 그것대로 '이유를 모르는 상승'이라는 정보가 된다.
    """
    by_code: dict[str, list[str]] = {}
    for item in disclosures:
        code = (getattr(item, "company_code", "") or "").strip()
        if code:
            by_code.setdefault(code, []).append(getattr(item, "title", ""))

    return [
        Surge(
            code=s.code,
            name=s.name,
            market=s.market,
            sector=s.sector,
            close=s.close,
            change_pct=s.change_pct,
            value=s.value,
            avg_value=s.avg_value,
            value_multiple=s.value_multiple,
            market_cap=s.market_cap,
            disclosures=by_code.get(s.code, [])[:3],
        )
        for s in surges
    ]


def surge_prompt_lines(surges: list[Surge]) -> list[str]:
    """급등 종목을 국내 픽 프롬프트의 '시장 반응 참고' 색으로 넣을 텍스트 라인.

    급등은 촉매가 아니라 반응이므로, 이 라인들은 pick 선정 근거가 아니라 이미 공시
    촉매로 뽑힌 pick 의 설명을 풍부하게 하는 용도로만 쓰인다(호출부 프롬프트 참고).
    """
    lines: list[str] = []
    for s in surges:
        disc = f" · 공시: {s.disclosures[0]}" if s.disclosures else " · 공시 없음"
        lines.append(
            f"- {s.name}({s.code}): 거래대금 평균의 {s.value_multiple:.1f}배 급증, "
            f"{s.change_pct:+.1f}%{disc}"
        )
    return lines
