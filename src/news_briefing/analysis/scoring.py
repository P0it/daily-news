"""공시 유형별 기본 점수 산정 (SIGNALS.md 2.1 + 2.3 기반).

Week 1: `score_report` — 제목 키워드 매칭만.
Week 2a: `score_with_context` — 금액·지분율·매수/매도 구분 등 정량 보정 추가.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["positive", "negative", "mixed", "neutral"]

# SIGNALS.md 2.1 표 — 우선순위대로
SIGNAL_WEIGHTS: list[tuple[str, int, Direction]] = [
    ("횡령", 95, "negative"),
    ("배임", 95, "negative"),
    ("감자결정", 90, "negative"),
    ("관리종목지정", 90, "negative"),
    ("최대주주변경", 85, "mixed"),
    ("영업(잠정)실적", 85, "mixed"),
    ("주요사항보고", 85, "mixed"),
    ("자기주식취득", 80, "positive"),
    ("합병", 80, "mixed"),
    ("단일판매", 75, "positive"),
    ("공급계약", 75, "positive"),
    ("대규모기업집단", 75, "neutral"),
    ("유상증자", 75, "mixed"),
    ("자기주식처분", 70, "mixed"),
    ("임원ㆍ주요주주", 70, "mixed"),
    ("전환사채", 70, "mixed"),
    ("무상증자", 60, "positive"),
    ("사업보고서", 55, "neutral"),
    ("반기보고서", 50, "neutral"),
    ("분기보고서", 45, "neutral"),
]

DEFAULT_SCORE = 30
DEFAULT_DIRECTION: Direction = "neutral"


def score_report(report_name: str) -> tuple[int, Direction]:
    """공시 제목에서 우선순위 키워드를 매칭해 (점수, 방향성) 반환."""
    for keyword, score, direction in SIGNAL_WEIGHTS:
        if keyword in report_name:
            return score, direction
    return DEFAULT_SCORE, DEFAULT_DIRECTION


@dataclass(frozen=True, slots=True)
class ScoringContext:
    """정량 보정 입력. 모두 optional — 값이 있을 때만 해당 규칙 적용."""

    amount: int | None = None              # 원 단위 (공시 금액)
    market_cap: int | None = None          # 원 단위 (시가총액)
    acquisition_method: str | None = None  # '장내매수' | '신탁' | 기타
    trade_type: str | None = None          # '매수' | '매도' (임원공시)
    stake_change_pct: float | None = None  # 지분율 변동 %
    is_ceo: bool = False
    is_largest_shareholder: bool = False


@dataclass(frozen=True, slots=True)
class ScoringResult:
    score: int
    direction: Direction


def score_with_context(report_name: str, ctx: ScoringContext) -> ScoringResult:
    """기본 점수 + 정량 보정. SIGNALS.md 2.3 규칙."""
    base_score, direction = score_report(report_name)
    bonus = 0

    # 자기주식취득 정량 보정 (SIGNALS.md 2.3 stacking)
    if "자기주식취득" in report_name:
        if ctx.amount and ctx.market_cap:
            ratio = ctx.amount / ctx.market_cap
            if ratio >= 0.01:
                bonus += 10
            if ratio >= 0.05:
                bonus += 15  # 누적 최대 +25
        if ctx.acquisition_method == "장내매수":
            bonus += 5

    # 임원·주요주주 매수/매도 방향성 분기
    if "임원" in report_name and "주주" in report_name:
        if ctx.trade_type == "매수":
            direction = "positive"
            if ctx.is_ceo:
                bonus += 15
            if ctx.amount and ctx.amount > 1_000_000_000:
                bonus += 10
        elif ctx.trade_type == "매도":
            direction = "negative"
            if ctx.stake_change_pct and ctx.stake_change_pct > 1.0:
                bonus += 15
            if ctx.is_largest_shareholder:
                bonus += 20

    final = min(100, base_score + bonus)
    return ScoringResult(score=final, direction=direction)


# SIGNALS.md 2.1 해외 대응 — 8-K Item 번호별
EDGAR_ITEM_WEIGHTS: dict[str, tuple[int, Direction]] = {
    "1.01": (75, "positive"),   # Material Definitive Agreement (신규 계약)
    "1.02": (75, "negative"),   # Termination of Material Agreement
    "2.01": (85, "mixed"),      # Completion of Acquisition/Disposition
    "2.02": (80, "mixed"),      # Results of Operations (실적 발표)
    "2.06": (95, "negative"),   # Material Impairments
    "3.01": (85, "negative"),   # Delisting / Failure to Satisfy Listing Rule
    "3.02": (75, "mixed"),      # Unregistered Sales of Equity
    "4.01": (90, "negative"),   # Changes in Registrant's Certifying Accountant
    "4.02": (90, "negative"),   # Non-reliance on Previously Issued Financials
    "5.02": (70, "mixed"),      # Departure / Appointment of Directors or Officers
    "5.07": (50, "neutral"),    # Submission of Matters to a Vote
    "7.01": (60, "neutral"),    # Regulation FD Disclosure
    "8.01": (60, "neutral"),    # Other Events
}


def score_edgar(*, form_type: str, items: str) -> tuple[int, Direction]:
    """SEC EDGAR form_type + items 기반 점수.

    - Form 4: 기본 70, mixed (실제 매수/매도 구분은 별도 파싱 필요)
    - 8-K: Item 번호 우선 매칭, 매칭 실패 시 기본 70
    - 기타 (10-K, 10-Q 등): 45, neutral
    """
    if form_type == "4":
        return 70, "mixed"

    if form_type == "8-K":
        for item_code, (score, direction) in EDGAR_ITEM_WEIGHTS.items():
            if item_code in items:
                return score, direction
        return 70, "neutral"

    return 45, "neutral"
