"""발굴 트랙 오케스트레이션 — 유니버스 로드 → 펀더멘털 수집 → 정량 스크린.

`screen` 커맨드의 본체. 이벤트 구동 morning 파이프라인과 분리된, 사용자가 명시적으로
실행하는 온디맨드 트랙이다. Phase 2 에서 LLM 심층 리서치(`deep_research`)가 숏리스트
위에 얹히고, Phase 3 에서 스냅샷 저장·앱 주입이 붙는다.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from news_briefing.analysis.llm import _call_claude
from news_briefing.analysis.screener import ScreenResult, screen
from news_briefing.collectors.fundamentals import fetch_fundamentals
from news_briefing.config import PROJECT_ROOT

log = logging.getLogger(__name__)

_UNIVERSE_PATH = PROJECT_ROOT / "data" / "universe.json"

# scope 별 숏리스트 크기.
TOP_N = 20

# LLM 심층 리서치 호출 timeout(초). 종목 다수를 한 번에 보므로 넉넉히.
_RESEARCH_TIMEOUT = 600


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    us: list[ScreenResult]
    kospi: list[ScreenResult]


def load_universe(path: Path | None = None) -> dict[str, list[str]]:
    """data/universe.json 로드. 없으면 빈 유니버스."""
    p = path or _UNIVERSE_PATH
    if not p.exists():
        log.warning("유니버스 파일 없음: %s — `python scripts/build_universe.py` 실행 필요", p)
        return {"us": [], "kospi": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"us": data.get("us", []), "kospi": data.get("kospi", [])}


def run_screen(*, top_n: int = TOP_N) -> DiscoveryResult:
    """유니버스를 펀더멘털 스크린해 scope 별 숏리스트 반환(LLM 없음)."""
    universe = load_universe()

    us_funds = fetch_fundamentals(universe["us"], scope="us")
    kospi_funds = fetch_fundamentals(universe["kospi"], scope="kospi")

    us = screen(us_funds, top_n=top_n)
    kospi = screen(kospi_funds, top_n=top_n)

    log.info("발굴 스크린 완료 US %d · KOSPI %d", len(us), len(kospi))
    return DiscoveryResult(us=us, kospi=kospi)


# ── 스냅샷 아이템 ──────────────────────────────────────────────────────────────


def _round(x: float | None, n: int = 2) -> float | None:
    return None if x is None else round(x, n)


def result_to_item(r: ScreenResult) -> dict:
    """ScreenResult → 스냅샷/JSON 용 기본 dict(정량 부분만, thesis 전)."""
    m = r.metrics
    return {
        "ticker": r.ticker,
        "name": r.name,
        "scope": r.scope,
        "sector": r.sector,
        "composite": r.composite,
        "valueScore": r.value_score,
        "qualityScore": r.quality_score,
        "growthScore": r.growth_score,
        "highlights": r.highlights,
        "metrics": {
            "trailingPe": _round(m.get("trailing_pe")),
            "forwardPe": _round(m.get("forward_pe")),
            "priceToBook": _round(m.get("price_to_book")),
            "peg": _round(m.get("peg")),
            "evToEbitda": _round(m.get("ev_to_ebitda")),
            "roe": _round(m.get("roe"), 4),
            "profitMargin": _round(m.get("profit_margin"), 4),
            "operatingMargin": _round(m.get("operating_margin"), 4),
            "debtToEquity": _round(m.get("debt_to_equity")),
            "revenueGrowth": _round(m.get("revenue_growth"), 4),
            "earningsGrowth": _round(m.get("earnings_growth"), 4),
        },
        # thesis 필드는 deep_research 에서 채움(없으면 null)
        "thesis": None,
        "whyUndiscovered": None,
        "keyRisks": None,
        "confirmCatalysts": None,
        "valuationNote": None,
        "relatedEtf": None,
    }


# ── LLM 심층 리서치 ───────────────────────────────────────────────────────────


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"


def _num(x: float | None) -> str:
    return "—" if x is None else f"{x:.1f}"


def _metrics_line(r: ScreenResult) -> str:
    m = r.metrics
    return (
        f"PER {_num(m.get('trailing_pe'))} / FwdPER {_num(m.get('forward_pe'))} / "
        f"PBR {_num(m.get('price_to_book'))} / PEG {_num(m.get('peg'))} / "
        f"EV/EBITDA {_num(m.get('ev_to_ebitda'))} / ROE {_pct(m.get('roe'))} / "
        f"영업이익률 {_pct(m.get('operating_margin'))} / "
        f"부채비율 {_num(m.get('debt_to_equity'))}% / "
        f"매출성장 {_pct(m.get('revenue_growth'))} / 이익성장 {_pct(m.get('earnings_growth'))}"
    )


_SYSTEM = """\
당신은 펀더멘털 가치투자 리서치 애널리스트다. 아래는 고정 유니버스를 정량 스크린해
저평가·우량·성장 점수 상위로 추린 종목들이다. 이들은 '오늘 무슨 일이 터져서'가 아니라
'재무가 조용히 좋아서' 올라온 발굴 후보다. 각 종목의 투자 논리를 한국어로 심층 분석해라.

규칙:
- 개인 투자 판단 보조용이므로 방향성은 명확해도 된다(저평가 매력/성장 지속성 등).
- 다만 정량 지표에 근거를 두고, 반드시 핵심 리스크를 함께 적는다(낙관 일변도 금지).
- 존댓말 '~요' 체. 느낌표 금지. '필독·긴급·강력매수' 같은 과장 카피 금지.
- why_undiscovered: 재무가 좋은데도 시장이 아직 주목하지 않는(저평가된) 이유 가설.
- confirm_catalysts: 이 논리가 맞다면 앞으로 확인될 신호(실적·가이던스·수주 등).
- 미국 종목은 related_etf 에 ISA·연금계좌에서 살 수 있는 국내 상장 추종 ETF 를
  제시한다(섹터/테마 근접). 적절한 국내 상품이 없으면 null.
- 코스피 종목은 related_etf 를 null 로 둔다.

출력은 JSON 배열만. 설명·코드펜스 금지. 각 원소:
{
  "ticker": "원본 ticker 그대로",
  "thesis": "2~3문장 투자 논리(왜 지금 저평가 우량 성장인지)",
  "why_undiscovered": "시장이 아직 안 본 이유 1문장",
  "key_risks": "핵심 리스크 1~2개",
  "confirm_catalysts": "논리 확인용 향후 신호 1~2개",
  "valuation_note": "밸류에이션 한 줄 코멘트(동종/과거 대비 등)",
  "related_etf": {"ticker": "ETF코드", "name": "ETF명", "confidence": "high|medium|low"} 또는 null
}"""


def _research_prompt(scope: str, rows: list[ScreenResult]) -> str:
    scope_ko = "미국" if scope == "us" else "코스피"
    lines = []
    for i, r in enumerate(rows, 1):
        factors = f"가치 {r.value_score}/우량 {r.quality_score}/성장 {r.growth_score}"
        lines.append(
            f"{i}. [{r.ticker}] {r.name or ''} ({r.sector or '—'}) "
            f"· 종합 {r.composite} ({factors})\n"
            f"   {_metrics_line(r)}"
        )
    return f"{_SYSTEM}\n\n## {scope_ko} 발굴 후보\n" + "\n".join(lines)


def _scan_objects(raw: str) -> list[dict]:
    """배열 괄호 없이 나열된 최상위 {...} 객체들을 brace 매칭으로 추출.

    LLM 이 산문 서두를 붙이거나 배열 괄호를 빠뜨린 경우의 복구 경로.
    """
    objs: list[dict] = []
    depth = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    objs.append(json.loads(raw[start : i + 1]))
                except json.JSONDecodeError:
                    pass
                start = -1
    return objs


def _parse_research(raw: str) -> dict[str, dict]:
    """LLM 출력 → {ticker: thesis dict}. 코드펜스/산문 방어."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[:-1])
    raw = raw.strip()
    items: list
    try:
        parsed = json.loads(raw)
        items = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                items = json.loads(m.group(0))
            except json.JSONDecodeError:
                items = _scan_objects(raw)
        else:
            # 배열 괄호 없이 객체만 나열한 경우 — 개별 {...} 추출
            items = _scan_objects(raw)
    if not items:
        log.warning("발굴 리서치 JSON 파싱 실패")
        return {}
    out: dict[str, dict] = {}
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        ticker = str(it.get("ticker") or "").strip()
        if ticker:
            out[ticker] = it
    return out


def _apply_thesis(item: dict, thesis: dict) -> None:
    """thesis dict 를 스냅샷 item 에 병합(필드 정규화)."""
    item["thesis"] = thesis.get("thesis") or None
    item["whyUndiscovered"] = thesis.get("why_undiscovered") or None
    item["keyRisks"] = thesis.get("key_risks") or None
    item["confirmCatalysts"] = thesis.get("confirm_catalysts") or None
    item["valuationNote"] = thesis.get("valuation_note") or None
    etf = thesis.get("related_etf")
    if isinstance(etf, dict) and etf.get("ticker") and etf.get("name"):
        item["relatedEtf"] = {
            "ticker": str(etf["ticker"]).strip(),
            "name": str(etf["name"]).strip(),
            "confidence": str(etf.get("confidence") or "low").strip(),
        }


def deep_research(result: DiscoveryResult, *, timeout: int = _RESEARCH_TIMEOUT) -> dict:
    """숏리스트에 LLM 심층 리서치를 얹어 scope 별 enriched item 리스트 반환.

    LLM 실패 시 해당 scope 는 정량 점수만 가진 item 으로 유지(부분 실패 허용).
    """
    enriched: dict[str, list[dict]] = {}
    for scope, rows in (("us", result.us), ("kospi", result.kospi)):
        items = [result_to_item(r) for r in rows]
        if rows:
            try:
                raw = _call_claude(_research_prompt(scope, rows), timeout=timeout, model="opus")
                theses = _parse_research(raw)
                for item in items:
                    th = theses.get(item["ticker"])
                    if th:
                        _apply_thesis(item, th)
                log.info("발굴 리서치 %s: %d/%d 종목 thesis", scope, len(theses), len(items))
            except Exception as e:
                log.warning("발굴 리서치 LLM 실패 scope=%s: %s — 정량 점수만 유지", scope, e)
        enriched[scope] = items
    return enriched
