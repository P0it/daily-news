"""거시경제 지표 수집기 — yfinance 기반 전날 종가 스냅샷.

LLM 호출 없음. 실패해도 빈 리스트를 반환해 파이프라인을 중단하지 않는다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# (ticker, display_name, currency, group)
_TARGETS: list[tuple[str, str, str, str]] = [
    # 미국 증시
    ("^GSPC", "S&P 500",      "USD", "us_equity"),
    ("^IXIC", "NASDAQ",       "USD", "us_equity"),
    ("^DJI",  "DOW",          "USD", "us_equity"),
    # 국내 증시
    ("^KS11", "KOSPI",        "KRW", "kr_equity"),
    ("^KQ11", "KOSDAQ",       "KRW", "kr_equity"),
    # 환율
    ("KRW=X", "USD/KRW",      "KRW", "fx"),
    # 원자재
    ("CL=F",  "WTI 원유",      "USD", "commodity"),
    ("GC=F",  "금",            "USD", "commodity"),
    # 채권 (수익률, %)
    ("^TNX",  "미 10Y 국채",   "%",   "bond"),
    # 공포 지수
    ("^VIX",  "VIX",          "",    "volatility"),
]


@dataclass(frozen=True, slots=True)
class MacroIndex:
    symbol: str
    ticker: str
    close: float
    change: float      # close - prev_close
    change_pct: float  # % 변화율 (소수점 2자리)
    currency: str
    group: str         # us_equity / kr_equity / fx / commodity / bond / volatility


def fetch_macro() -> list[MacroIndex]:
    """yfinance 로 최근 2거래일 종가를 가져와 변화율을 계산한다."""
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance 미설치 — macro 수집 스킵. `uv add yfinance` 로 설치하세요.")
        return []

    tickers = [t for t, *_ in _TARGETS]
    try:
        # period="5d": 공휴일/주말로 2거래일이 비는 경우를 대비해 넉넉히 요청
        raw = yf.download(
            tickers,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=True,
        )
    except Exception as e:
        log.error("yfinance 다운로드 실패: %s", e)
        return []

    close_df = raw.get("Close")
    if close_df is None or close_df.empty:
        log.warning("yfinance Close 데이터 없음")
        return []

    results: list[MacroIndex] = []
    for ticker, symbol, currency, group in _TARGETS:
        try:
            series = close_df[ticker].dropna()
            if len(series) < 2:
                log.debug("데이터 부족 ticker=%s rows=%d", ticker, len(series))
                continue
            close_val = float(series.iloc[-1])
            prev_val = float(series.iloc[-2])
            change = round(close_val - prev_val, 4)
            change_pct = round((change / prev_val) * 100, 2) if prev_val else 0.0
            results.append(
                MacroIndex(
                    symbol=symbol,
                    ticker=ticker,
                    close=round(close_val, 2),
                    change=change,
                    change_pct=change_pct,
                    currency=currency,
                    group=group,
                )
            )
        except Exception as e:
            log.warning("macro 개별 ticker 실패 ticker=%s err=%s", ticker, e)

    log.info("macro 수집 완료 %d/%d", len(results), len(_TARGETS))
    return results
