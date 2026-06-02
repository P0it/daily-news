"""주목도 사이클 위상 분류기 (Attention Cycle Phase Classifier).

Phase 1 (미발견): 선행 시그널 등장, 가격 미반영, 주목도 낮음  → 최우선 매수 후보
Phase 2 (초기 주목): 주목도 가속 중, 일부 반영 시작           → 진입 가능
Phase 3 (주류): 언론 도배, 이미 상승                          → 주의 경고
Phase 4 (포화): 고점권 횡보, 주목도 식어감                    → 회피

개미보다 빠른 것이 목표 — 기관 대비 선행이 아니라, 대중 주목도 곡선의 초입 포착.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

PHASE_LABELS: dict[int, str] = {
    1: "초기 진입 구간",
    2: "상승 초반",
    3: "주의 — 이미 주목받는 중",
    4: "고점 경계",
}

# Phase 3 이상은 Today's Pick 상단 노출에서 제외 (경고 표시는 함)
PHASE_WARN_THRESHOLD = 3
PHASE_EXCLUDE_THRESHOLD = 4


@dataclass(frozen=True, slots=True)
class AttentionPhase:
    phase: int           # 1~4
    label: str           # 한국어 라벨
    trend_accel: float   # Google Trends 가속도 (이번 주 / 4주 평균 - 1)
    price_lead: float    # 시그널 발생 전 5거래일 수익률 (0=티커 없음)
    signal_diversity: float  # 활성 소스 비율 0~1


def _fetch_trend_accel(keyword: str) -> float:
    """Google Trends 4주 이동평균 대비 이번 주 상승률.

    pytrends 미설치·네트워크 오류 시 0.0 반환.
    절대값이 아닌 변화율 — 이미 높은 수준이 아니라 '지금 올라가는 중'인지가 핵심.
    """
    try:
        from pytrends.request import TrendReq

        kw = keyword[:100]
        pt = TrendReq(hl="ko", tz=540, timeout=(5, 15))
        pt.build_payload([kw], timeframe="today 3-m", geo="KR")
        df = pt.interest_over_time()
        if df.empty or kw not in df.columns:
            return 0.0
        values = df[kw].astype(float).values
        if len(values) < 5:
            return 0.0
        last = float(values[-1])
        avg4w = float(values[-5:-1].mean())
        if avg4w < 1.0:
            return 1.0 if last > 0 else 0.0
        return last / avg4w - 1.0
    except Exception as e:
        log.debug("Google Trends 조회 실패 %r: %s", keyword, e)
        return 0.0


def _fetch_prices_batch(
    code_to_ticker: dict[str, str], lookback_days: int = 5
) -> dict[str, float]:
    """여러 티커 한 번에 yfinance 조회 → {company_code: 5일 수익률}.

    KS/KQ 병렬 시도: 한 번 실패하면 다른 suffix 사용.
    """
    if not code_to_ticker:
        return {}
    try:
        import yfinance as yf

        tickers_ks = [f"{c}.KS" for c in code_to_ticker]
        raw = yf.download(
            tickers_ks,
            period="15d",
            progress=False,
            auto_adjust=True,
            threads=True,
            group_by="ticker",
        )
        result: dict[str, float] = {}
        for code, ticker_ks in zip(code_to_ticker, tickers_ks):
            try:
                if len(code_to_ticker) == 1:
                    close = raw["Close"].values.flatten()
                else:
                    close = raw[ticker_ks]["Close"].values.flatten()
                close = close[~__import__("numpy").isnan(close)]
                if len(close) < lookback_days:
                    raise ValueError("데이터 부족")
                start = float(close[max(0, len(close) - lookback_days - 1)])
                end = float(close[-1])
                if start > 0:
                    result[code] = (end - start) / start
            except Exception:
                result[code] = 0.0
        return result
    except Exception as e:
        log.debug("yfinance 배치 조회 실패: %s", e)
        return {}


def classify_phase(
    *,
    trend_accel: float,
    price_lead: float,
    signal_diversity: float,
    news_accel: float = 0.0,
) -> tuple[int, str]:
    """4개 위상 분류 → (phase_int, label) 반환.

    news_accel: 오늘 관련 뉴스 건수 / 7일 일평균 - 1 (0이면 비교 불가)
    signal_diversity: 켜진 소스 종류 수 / 총 소스 종류 수 (0~1)
    """
    # Phase 4: 이미 크게 올랐는데 주목도가 꺾임 (뒷북 매수 위험)
    if price_lead > 0.15 and (trend_accel < 0.0 or news_accel < -0.3):
        return 4, PHASE_LABELS[4]
    # Phase 3: 주류 (뉴스·트렌드 폭발 또는 가격 이미 선반영)
    if trend_accel > 1.5 or news_accel > 2.0 or price_lead > 0.10:
        return 3, PHASE_LABELS[3]
    # Phase 2: 초기 주목 (여러 소스 동시 점화 또는 트렌드 가속)
    if signal_diversity >= 0.5 or trend_accel > 0.3 or news_accel > 0.5:
        return 2, PHASE_LABELS[2]
    # Phase 1: 미발견 (단일 소스, 가격 미반영, 관심 낮음)
    return 1, PHASE_LABELS[1]


def build_phase_map(
    scored: list[tuple],
    *,
    enable_gtrends: bool = False,
    enable_price: bool = True,
    total_source_types: int = 3,
) -> dict[str, AttentionPhase]:
    """scored 리스트 → {ext_id: AttentionPhase} 매핑.

    Args:
        scored: [(CollectedItem, score, direction), ...]
        enable_gtrends: True 시 Google Trends 호출 (느림, 기본 비활성)
        enable_price: yfinance 가격 조회 여부 (기본 활성)
        total_source_types: 비교 분모 소스 종류 수 (dart/edgar/research)
    """
    if not scored:
        return {}

    # 1. company_code별 활성 소스 다양성 집계
    code_to_sources: dict[str, set[str]] = {}
    for item, _, _ in scored:
        code = item.company_code or item.company or item.ext_id
        src = item.source.split(":")[0]
        code_to_sources.setdefault(code, set()).add(src)

    # 2. yfinance 배치 조회 (6자리 코드 = 국내 종목)
    domestic_codes = {
        item.company_code
        for item, _, _ in scored
        if item.company_code and item.company_code.isdigit() and len(item.company_code) == 6
    }
    price_map: dict[str, float] = {}
    if enable_price and domestic_codes:
        price_map = _fetch_prices_batch(
            {c: f"{c}.KS" for c in domestic_codes}
        )

    # 3. 위상 분류
    result: dict[str, AttentionPhase] = {}
    for item, _score, _ in scored:
        code = item.company_code or item.company or item.ext_id
        active = len(code_to_sources.get(code, set()))
        diversity = min(1.0, active / max(1, total_source_types))

        trend_accel = 0.0
        if enable_gtrends and item.company:
            trend_accel = _fetch_trend_accel(item.company)

        price_lead = price_map.get(item.company_code or "", 0.0)

        phase_int, phase_label = classify_phase(
            trend_accel=trend_accel,
            price_lead=price_lead,
            signal_diversity=diversity,
        )
        result[item.ext_id] = AttentionPhase(
            phase=phase_int,
            label=phase_label,
            trend_accel=trend_accel,
            price_lead=price_lead,
            signal_diversity=diversity,
        )

    return result
