"""국내 주요 ETF 시세 수집기 — yfinance 기반.

KRX 공식 API는 세션 인증이 필요해 불안정하므로 yfinance 를 사용한다.
주요 테마별 대표 ETF를 수집해 자금 흐름 파악에 활용한다. LLM 호출 없음.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# (ticker, display_name, theme)
# 테마별 대표 ETF — 섹터 편중 없이 전체 시장 커버
_ETF_TARGETS: list[tuple[str, str, str]] = [
    # 시장 대표
    ("069500.KS", "KODEX 200",          "대형주"),
    ("102110.KS", "TIGER 200",          "대형주"),
    ("229200.KS", "KODEX KOSDAQ150",    "코스닥"),
    # 미국 증시
    ("261220.KS", "KODEX 미국S&P500",   "미국주식"),
    ("133690.KS", "TIGER 미국나스닥100", "미국주식"),
    # 채권·안전자산
    ("148070.KS", "KOSEF 국고채10년",   "채권"),
    ("132030.KS", "KODEX 골드선물",     "원자재"),
    # 성장 테마
    ("091160.KS", "KODEX 반도체",       "반도체"),
    ("305720.KS", "KODEX 2차전지산업",  "2차전지"),
    ("364980.KS", "TIGER Fn반도체TOP10","반도체"),
    ("139220.KS", "TIGER 200 IT",       "IT"),
    ("448290.KS", "TIGER 미국AI빅테크10","AI/빅테크"),
    # 배당·인컴
    ("280930.KS", "TIGER 코스피고배당",  "배당"),
    # 금융·에너지
    ("091170.KS", "KODEX 은행",         "금융"),
    ("139270.KS", "TIGER 200 에너지화학","에너지"),
]


@dataclass(frozen=True, slots=True)
class ETFSnapshot:
    code: str        # 종목코드 (069500 등)
    name: str        # ETF명
    theme: str       # 테마 분류
    close: float     # 종가 (원)
    change: float    # 전일대비 (원)
    change_pct: float  # 등락률 (%)


def fetch_krx_etf() -> list[ETFSnapshot]:
    """주요 국내 ETF 전날 종가 스냅샷을 반환한다."""
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance 미설치 — ETF 수집 스킵.")
        return []

    tickers = [t for t, *_ in _ETF_TARGETS]
    try:
        raw = yf.download(
            tickers,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=True,
        )
    except Exception as e:
        log.error("yfinance ETF 다운로드 실패: %s", e)
        return []

    close_df = raw.get("Close")
    if close_df is None or close_df.empty:
        log.warning("ETF Close 데이터 없음")
        return []

    results: list[ETFSnapshot] = []
    for ticker, name, theme in _ETF_TARGETS:
        try:
            series = close_df[ticker].dropna()
            if len(series) < 2:
                continue
            close_val = float(series.iloc[-1])
            prev_val = float(series.iloc[-2])
            change = round(close_val - prev_val, 2)
            change_pct = round((change / prev_val) * 100, 2) if prev_val else 0.0
            code = ticker.split(".")[0]
            results.append(
                ETFSnapshot(
                    code=code,
                    name=name,
                    theme=theme,
                    close=round(close_val, 2),
                    change=change,
                    change_pct=change_pct,
                )
            )
        except Exception as e:
            log.debug("ETF 개별 ticker 실패 ticker=%s: %s", ticker, e)

    log.info("ETF 수집 완료 %d/%d", len(results), len(_ETF_TARGETS))
    return results
