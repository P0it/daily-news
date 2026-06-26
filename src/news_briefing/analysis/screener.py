"""펀더멘털 발굴 스크린 — 결정론적 정량 랭킹 (LLM 없음).

이 모듈이 발굴 트랙의 '메커니즘' 본체다. 이벤트 구동 picks(`hot_issues.py`)와 달리,
고정 유니버스의 펀더멘털(`collectors/fundamentals.py`)을 **유니버스 내 백분위**로
랭킹해 '저평가 + 재무 탄탄 + 성장' 종목을 추린다.

설계 원칙:
- **상대 평가**: 절대 임계값(PER<10 등)은 섹터·시장마다 의미가 달라, 유니버스 내
  백분위로 랭크한다. 같은 풀에서 상대적으로 싸고/좋고/성장하는 종목을 찾는다.
- **결측 견딤**: yfinance 결측이 흔하므로, 가용 지표만으로 팩터를 만들고 없는 팩터는
  가중치에서 제외한다. 평가 자체가 불가능한 종목만 버린다.
- **재현성**: 동일 입력 → 동일 출력. 외부 의존·난수 없음(단위 테스트 대상).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from news_briefing.collectors.fundamentals import Fundamentals

# 팩터 가중치(합 1.0). '저평가 우량 성장' 목표상 가치·퀄리티에 무게.
WEIGHTS: dict[str, float] = {"value": 0.35, "quality": 0.35, "growth": 0.30}

# 팩터별 지표: (속성명, lower_is_better, positive_only)
# positive_only=True 면 0 이하 값은 결측 취급(적자 PER 은 '싼' 게 아니라 평가 불가).
_VALUE = [
    ("trailing_pe", True, True),
    ("forward_pe", True, True),
    ("price_to_book", True, True),
    ("ev_to_ebitda", True, True),
    ("peg", True, True),
    ("fcf_yield", False, False),  # 계산 지표 = free_cashflow / market_cap
]
_QUALITY = [
    ("roe", False, False),
    ("profit_margin", False, False),
    ("operating_margin", False, False),
    ("debt_to_equity", True, True),  # 낮을수록 좋음. 음수(자본잠식)는 결측 처리 후 정크필터
]
_GROWTH = [
    ("revenue_growth", False, False),
    ("earnings_growth", False, False),
]
_FACTORS = {"value": _VALUE, "quality": _QUALITY, "growth": _GROWTH}

# 정크 필터: 평가가 무의미한 종목 제외.
_MAX_DEBT_TO_EQUITY = 400.0  # 400% 초과 과다부채 제외(금융/유틸 일부 희생 감수)
_MIN_METRICS = 4  # 최소 가용 핵심 지표 수(이하면 데이터 부족으로 제외)


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """한 종목의 스크린 결과. 점수는 0~100."""

    ticker: str
    name: str | None
    scope: str
    sector: str | None
    composite: int
    value_score: int | None
    quality_score: int | None
    growth_score: int | None
    metrics: dict[str, float | None]
    highlights: list[str] = field(default_factory=list)


def _metric_map(f: Fundamentals) -> dict[str, float | None]:
    """Fundamentals → 지표 dict(계산 지표 fcf_yield 포함)."""
    fcf_yield: float | None = None
    if f.free_cashflow is not None and f.market_cap and f.market_cap > 0:
        fcf_yield = f.free_cashflow / f.market_cap
    return {
        "trailing_pe": f.trailing_pe,
        "forward_pe": f.forward_pe,
        "price_to_book": f.price_to_book,
        "ev_to_ebitda": f.ev_to_ebitda,
        "peg": f.peg,
        "fcf_yield": fcf_yield,
        "roe": f.roe,
        "profit_margin": f.profit_margin,
        "operating_margin": f.operating_margin,
        "debt_to_equity": f.debt_to_equity,
        "revenue_growth": f.revenue_growth,
        "earnings_growth": f.earnings_growth,
    }


def _clean(value: float | None, positive_only: bool) -> float | None:
    """positive_only 지표의 0 이하 값을 결측으로."""
    if value is None:
        return None
    if positive_only and value <= 0:
        return None
    return value


def _percentile(sorted_vals: list[float], x: float) -> float:
    """유니버스 내 x 의 중간순위 백분위 ∈ (0,1). 동률 대칭 처리."""
    n = len(sorted_vals)
    less = sum(1 for v in sorted_vals if v < x)
    eq = sum(1 for v in sorted_vals if v == x)
    return (less + 0.5 * eq) / n


def _is_junk(m: dict[str, float | None]) -> bool:
    """평가가 무의미한 종목인지. True 면 스크린에서 제외."""
    # 과다부채
    de = m.get("debt_to_equity")
    if de is not None and de > _MAX_DEBT_TO_EQUITY:
        return True
    # 적자 + 성장 스토리 없음 → 발굴 가치 없음
    pm = m.get("profit_margin")
    eg = m.get("earnings_growth")
    rg = m.get("revenue_growth")
    if pm is not None and pm < 0:
        growth_story = (eg is not None and eg > 0.20) or (rg is not None and rg > 0.20)
        if not growth_story:
            return True
    # 가용 지표 부족
    present = sum(1 for v in m.values() if v is not None)
    if present < _MIN_METRICS:
        return True
    return False


def _factor_percentiles(
    cleaned: list[dict[str, float | None]],
    specs: list[tuple[str, bool, bool]],
) -> list[dict[str, float]]:
    """각 종목의 팩터 내 지표별 백분위(0~1, 높을수록 좋음)를 계산.

    반환: 종목별 {지표명: 백분위} (해당 지표가 결측인 종목은 키 없음).
    """
    # 지표별 유니버스 분포 미리 정렬
    columns: dict[str, list[float]] = {}
    for attr, _lower, _pos in specs:
        vals = [m[attr] for m in cleaned if m[attr] is not None]
        columns[attr] = sorted(vals)

    out: list[dict[str, float]] = []
    for m in cleaned:
        ranks: dict[str, float] = {}
        for attr, lower_is_better, _pos in specs:
            x = m[attr]
            col = columns[attr]
            if x is None or not col:
                continue
            pct = _percentile(col, x)
            ranks[attr] = (1.0 - pct) if lower_is_better else pct
        out.append(ranks)
    return out


def screen(
    funds: list[Fundamentals],
    *,
    top_n: int = 20,
    weights: dict[str, float] | None = None,
) -> list[ScreenResult]:
    """유니버스 펀더멘털을 백분위 합성점수로 랭킹해 상위 top_n 반환.

    Args:
        funds: 한 scope(us/kospi)의 Fundamentals 리스트.
        top_n: 반환할 숏리스트 크기.
        weights: 팩터 가중치 override(기본 WEIGHTS).
    """
    weights = weights or WEIGHTS
    if not funds:
        return []

    # 1) 지표화 + positive_only 정리 + 정크 제외
    raw = [(_metric_map(f), f) for f in funds]
    cleaned_pairs: list[tuple[dict[str, float | None], Fundamentals]] = []
    for m, f in raw:
        cm: dict[str, float | None] = {}
        for factor_specs in _FACTORS.values():
            for attr, _lower, pos in factor_specs:
                cm[attr] = _clean(m[attr], pos)
        if _is_junk(cm):
            continue
        cleaned_pairs.append((cm, f))

    if not cleaned_pairs:
        return []

    cleaned = [cm for cm, _ in cleaned_pairs]

    # 2) 팩터별 백분위
    factor_ranks: dict[str, list[dict[str, float]]] = {
        name: _factor_percentiles(cleaned, specs) for name, specs in _FACTORS.items()
    }

    # 3) 종목별 팩터 점수 + 가중 합성
    results: list[ScreenResult] = []
    for i, (cm, f) in enumerate(cleaned_pairs):
        factor_scores: dict[str, float | None] = {}
        for name in _FACTORS:
            ranks = factor_ranks[name][i]
            factor_scores[name] = (sum(ranks.values()) / len(ranks)) if ranks else None

        # 가용 팩터만으로 가중치 재정규화
        avail = {n: s for n, s in factor_scores.items() if s is not None}
        if not avail:
            continue
        wsum = sum(weights[n] for n in avail)
        composite = sum(weights[n] * s for n, s in avail.items()) / wsum

        highlights = _highlights(factor_scores)
        results.append(
            ScreenResult(
                ticker=f.ticker,
                name=f.name,
                scope=f.scope,
                sector=f.sector,
                composite=round(composite * 100),
                value_score=_pct100(factor_scores["value"]),
                quality_score=_pct100(factor_scores["quality"]),
                growth_score=_pct100(factor_scores["growth"]),
                metrics=cm,
                highlights=highlights,
            )
        )

    results.sort(key=lambda r: r.composite, reverse=True)
    return results[:top_n]


def _pct100(x: float | None) -> int | None:
    return None if x is None else round(x * 100)


def _highlights(factor_scores: dict[str, float | None]) -> list[str]:
    """강한 팩터(백분위 0.7+)를 한국어 라벨로."""
    label = {"value": "저평가", "quality": "재무우량", "growth": "성장"}
    return [label[n] for n, s in factor_scores.items() if s is not None and s >= 0.70]
