"""펀더멘털 지표 수집기 — yfinance 기반.

발굴 스크린(`analysis/screener.py`)의 입력. 이벤트 구동 촉매 수집기들과 달리, 고정
유니버스(`data/universe.json`)의 각 종목에 대해 밸류에이션·수익성·성장 지표를 가져온다.

LLM 호출 없음. 한 종목 실패가 전체를 멈추지 않도록 개별 예외를 잡아 스킵한다
(CLAUDE.md 에러 처리 원칙). FMP 유료 미사용 — yfinance 무료 데이터만(P2 무과금).

주의: yfinance `.info` 는 종목·시장별로 결측이 흔하다(코스피는 trailingPE·priceToBook 가
None 인 경우 많음). 결측은 None 으로 두고, 스크리너가 가용 지표만으로 랭킹한다.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

log = logging.getLogger(__name__)

# 동시 .info 호출 수. yfinance 레이트리밋을 피하려 보수적으로.
_MAX_WORKERS = 8


@dataclass(frozen=True, slots=True)
class Fundamentals:
    """한 종목의 펀더멘털 스냅샷. 결측 지표는 None.

    단위 메모(yfinance 규약): 비율 지표(roe·각종 margin·growth)는 소수(0.18 = 18%),
    debt_to_equity 는 퍼센트(79.5 = 79.5%), per/pbr/peg/ev_ebitda 는 배수.
    """

    ticker: str
    scope: str  # "us" | "kospi"
    name: str | None
    sector: str | None
    currency: str | None
    market_cap: float | None
    trailing_pe: float | None
    forward_pe: float | None
    price_to_book: float | None
    peg: float | None
    ev_to_ebitda: float | None
    roe: float | None
    profit_margin: float | None
    operating_margin: float | None
    debt_to_equity: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    free_cashflow: float | None

    def to_row(self) -> dict:
        """Supabase 저장용 dict (dataclass 그대로)."""
        return asdict(self)


def _f(info: dict, key: str) -> float | None:
    """info 에서 숫자 값을 안전하게 추출. 숫자가 아니면 None."""
    val = info.get(key)
    if val is None:
        return None
    try:
        out = float(val)
    except (TypeError, ValueError):
        return None
    # yfinance 가 가끔 inf/NaN 을 흘리므로 방어
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _fetch_one(ticker: str, scope: str) -> Fundamentals | None:
    """단일 종목 펀더멘털. 실패 시 None(로그만)."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        if not info or info.get("quoteType") == "MUTUALFUND":
            return None
        # peg 는 키가 버전마다 달라 두 후보를 본다
        peg = _f(info, "trailingPegRatio")
        if peg is None:
            peg = _f(info, "pegRatio")
        return Fundamentals(
            ticker=ticker,
            scope=scope,
            name=info.get("shortName") or info.get("longName"),
            sector=info.get("sector"),
            currency=info.get("currency"),
            market_cap=_f(info, "marketCap"),
            trailing_pe=_f(info, "trailingPE"),
            forward_pe=_f(info, "forwardPE"),
            price_to_book=_f(info, "priceToBook"),
            peg=peg,
            ev_to_ebitda=_f(info, "enterpriseToEbitda"),
            roe=_f(info, "returnOnEquity"),
            profit_margin=_f(info, "profitMargins"),
            operating_margin=_f(info, "operatingMargins"),
            debt_to_equity=_f(info, "debtToEquity"),
            revenue_growth=_f(info, "revenueGrowth"),
            earnings_growth=_f(info, "earningsGrowth"),
            free_cashflow=_f(info, "freeCashflow"),
        )
    except Exception as e:
        log.debug("펀더멘털 수집 실패 ticker=%s err=%s", ticker, e)
        return None


def fetch_fundamentals(tickers: list[str], scope: str) -> list[Fundamentals]:
    """유니버스 종목들의 펀더멘털을 병렬 수집. 실패 종목은 빠진 채 반환.

    Args:
        tickers: yfinance 심볼 리스트(코스피는 .KS 접미사).
        scope: "us" | "kospi".
    """
    try:
        import yfinance  # noqa: F401
    except ImportError:
        log.warning("yfinance 미설치 — 펀더멘털 수집 스킵. `uv add yfinance`.")
        return []

    results: list[Fundamentals] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        for f in pool.map(lambda t: _fetch_one(t, scope), tickers):
            if f is not None:
                results.append(f)

    log.info("펀더멘털 수집 완료 scope=%s %d/%d", scope, len(results), len(tickers))
    return results
