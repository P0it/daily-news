"""LLM 기반 '오늘의 주목 종목/테마' 분석.

해외(foreign): EDGAR·FT·BBC 등 Tier 1 해외 소스 우선.
국내(domestic): DART 공시·증권사 리포트·한경·매경 소스 우선.
뉴스 나열 대신 투자 대상(종목·테마)을 먼저 제시하고 근거 기사를 함께 반환한다.
"""
from __future__ import annotations

import json
import logging

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

# ── 해외용 소스 티어 ─────────────────────────────────────────────
_TIER_MAP_FOREIGN: dict[str, int] = {
    "edgar":                 1,
    "rss:ft-markets":        1,
    "rss:bbc-business":      1,
    "rss:bbc-world":         1,
    "rss:gnews-world-en":    2,
    "rss:gnews-business-en": 2,
    "rss:gnews-tech-en":     2,
    "rss:yonhap-intl":       2,
}

# ── 국내용 소스 티어 ─────────────────────────────────────────────
_TIER_MAP_DOMESTIC: dict[str, int] = {
    "dart":                  1,  # DART 공시 최우선
    "research":              1,  # 증권사 리포트
    "rss:hankyung":          2,
    "rss:mk":                2,
    "rss:yonhap-kr":         2,
    "rss:gnews-business-kr": 3,
    "rss:gnews-stock-kr":    3,
}

_DEFAULT_TIER = 3

# ── 표시용 언론사명 ──────────────────────────────────────────────
_DISPLAY_MAP: dict[str, str] = {
    "edgar":                 "SEC EDGAR",
    "dart":                  "DART",
    "research":              "증권사 리포트",
    "rss:ft-markets":        "Financial Times",
    "rss:bbc-business":      "BBC Business",
    "rss:bbc-world":         "BBC World",
    "rss:gnews-world-en":    "Google News (World)",
    "rss:gnews-business-en": "Google News (Business)",
    "rss:gnews-tech-en":     "Google News (Tech)",
    "rss:yonhap-intl":       "연합뉴스 국제",
    "rss:yonhap-kr":         "연합뉴스",
    "rss:hankyung":          "한국경제",
    "rss:mk":                "매일경제",
    "rss:gnews-business-kr": "Google News (경제)",
    "rss:gnews-stock-kr":    "Google News (증시)",
}


def source_tier_foreign(source: str) -> int:
    return _TIER_MAP_FOREIGN.get(source, _DEFAULT_TIER)


def source_tier_domestic(source: str) -> int:
    return _TIER_MAP_DOMESTIC.get(source, _DEFAULT_TIER)


def source_display(source: str) -> str:
    return _DISPLAY_MAP.get(source, source)


_PROMPT_SYSTEM = """\
너는 해외 주식 투자자를 위한 투자 리서치 에디터다.
아래 오늘 수집된 기사·공시 목록을 분석해, 오늘 당장 주목해야 할 종목·테마·자산 3개를 선정하라.

핵심 원칙:
- 뉴스 자체가 아니라 **투자 대상(종목·테마·자산)**을 먼저 제시한다
- 기사·공시는 그 주장의 근거로만 사용한다
- Tier 1 소스(SEC EDGAR·Financial Times·BBC)를 우선 참고한다
- 미국·글로벌 투자자 관점 (한국 내수 테마 제외)

선정 기준 (우선순위):
1. SEC EDGAR 8-K 공시: 기업 실적·가이던스·M&A·구조조정 직접 공시
2. 중앙은행·정부 정책 발표: 금리·규제·무역 정책이 특정 섹터/자산에 미치는 영향
3. FT·BBC 단독 보도: 시장 가격에 아직 반영 안 된 새로운 정보
4. 매크로 변화: 달러·금리·원자재 흐름이 특정 ETF·섹터로 직결

picks 작성 원칙 (★ 핵심):
- "이 이슈로 인해 오늘 사거나 주목할 구체적인 종목·ETF"를 2~3개 제시
- direction=negative(예: 유가 하락)이면 그로 인해 **수혜받는** 종목(예: 항공주·소비재)을 picks로 제시
- direction=positive(예: 로봇 테마 급부상)이면 **직접 수혜** 종목을 picks로 제시
- picks는 이슈 자체가 아닌 파생 투자 대상임. 이슈와 picks가 같아선 안 됨
- 국내 추종 ETF: ISA·연금 계좌에서 매수 가능한 국내 ETF를 반드시 병기. 없으면 null

출력 규칙:
- JSON 배열만 반환. 마크다운 코드블록·설명 텍스트 없이 배열 그대로.
- 배열 길이 정확히 3.
- 각 원소:
  {
    "rank": 숫자,
    "asset": "이슈 대상 이름. 종목이면 티커(예: NVDA), 테마면 짧은 한국어(예: 에너지·반도체), 매크로면 자산명(예: WTI원유). 절대 뉴스 제목을 쓰지 말 것.",
    "assetType": "stock" | "theme" | "macro",
    "direction": "positive" | "negative" | "mixed",
    "signal": "핵심 시그널 15자 이내 (예: 가이던스 상향, 금리 동결, 규제 리스크)",
    "reason": "왜 오늘 이 자산에 주목해야 하는지 2~3문장, '~요'체, 구체적 수치 포함",
    "cautions": "이 thesis가 뒤집힐 수 있는 핵심 리스크 1~2문장, '~요'체. 구체적이고 실질적인 것만. 리스크가 없으면 null.",
    "picks": [
      {
        "ticker": "미국 심볼 (예: JETS, DAL, XLY)",
        "name": "한국어 기업·펀드명 (예: 미국항공 ETF, 델타항공, 소비재 ETF)",
        "description": "이 종목을 추천하는 이유와 어떤 현상/메커니즘으로 수혜가 예상되는지 1~2문장, '~요'체",
        "domestic": {
          "ticker": "국내 ETF 종목코드 (예: 261110)",
          "name": "국내 ETF명 (예: TIGER 미국항공우주)"
        }
      }
    ],
    "source": "출처 언론사명",
    "url": "원문 URL 또는 null"
  }
  picks 배열은 2~3개. domestic이 없으면 "domestic": null.
"""

_PROMPT_SYSTEM_DOMESTIC = """\
너는 코스피·코스닥 투자자를 위한 국내 주식 리서치 에디터다.
아래 오늘 수집된 DART 공시·증권사 리포트·국내 경제 뉴스를 분석해,
오늘 당장 주목해야 할 국내 종목·테마 3개를 선정하라.

핵심 원칙:
- 코스피·코스닥 투자자 관점 (해외 종목 제외)
- DART 공시 최우선 (실적·가이던스·M&A·자사주·유무상증자 직접 공시)
- 증권사 목표주가 상향/신규 커버리지도 중요한 시그널
- 한국 내수·수출·산업 테마 포함 가능

선정 기준 (우선순위):
1. DART 공시: 어닝 서프라이즈·가이던스 상향·M&A·자사주 매입 등 직접 촉매
2. 증권사 리포트: 목표주가 상향(10% 이상) 또는 신규 커버리지 개시
3. 국내 경제 뉴스: 정부 정책·규제 변화가 특정 섹터에 미치는 영향
4. 테마 시그널: 동일 섹터 내 복수 기업에 영향을 주는 구조적 변화

picks 작성 원칙 (★ 핵심):
- "이 이슈로 오늘 사거나 주목할 구체적인 국내 종목·ETF" 2~3개 제시
- ticker는 한국 종목코드(6자리 숫자, 예: 005930) 또는 ETF 코드
- domestic 필드는 반드시 null (picks 자체가 국내 종목이므로 불필요)
- direction=negative(예: 원자재 가격 하락)이면 수혜받는 국내 종목을 picks로 제시

출력 규칙:
- JSON 배열만 반환. 마크다운 코드블록·설명 텍스트 없이 배열 그대로.
- 배열 길이 정확히 3.
- 각 원소:
  {
    "rank": 숫자,
    "asset": "이슈 대상. 종목이면 기업명(예: 삼성전자), 테마면 짧은 한국어(예: 2차전지·방산), 매크로면 자산명. 절대 뉴스 제목을 쓰지 말 것.",
    "assetType": "stock" | "theme" | "macro",
    "direction": "positive" | "negative" | "mixed",
    "signal": "핵심 시그널 15자 이내 (예: 목표주가 상향, 어닝 서프라이즈, 자사주 매입)",
    "reason": "왜 오늘 이 자산에 주목해야 하는지 2~3문장, '~요'체, 구체적 수치 포함",
    "cautions": "이 thesis가 뒤집힐 수 있는 핵심 리스크 1~2문장, '~요'체. 구체적이고 실질적인 것만. 리스크가 없으면 null.",
    "picks": [
      {
        "ticker": "한국 종목코드 6자리 (예: 005930)",
        "name": "기업명 또는 ETF명 (예: 삼성전자, KODEX 2차전지산업)",
        "description": "이 종목을 추천하는 이유와 수혜 메커니즘 1~2문장, '~요'체",
        "domestic": null
      }
    ],
    "source": "출처 언론사·기관명",
    "url": "원문 URL 또는 null"
  }
  picks 배열은 2~3개. domestic은 항상 null.
"""


def _parse_issues(raw: str) -> list[dict]:
    """LLM 출력 → 검증된 HotIssue 리스트. 공통 파싱 로직."""
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[:-1])
    raw = raw.strip()

    issues: list[dict] = json.loads(raw)
    validated: list[dict] = []
    for iss in issues[:3]:
        asset = str(iss.get("asset") or iss.get("title") or "").strip()
        if not asset:
            continue
        raw_picks = iss.get("picks") or []
        picks: list[dict] = []
        for p in raw_picks[:3]:
            if not isinstance(p, dict):
                continue
            ticker = str(p.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            domestic_raw = p.get("domestic")
            domestic = None
            if isinstance(domestic_raw, dict):
                d_ticker = str(domestic_raw.get("ticker") or "").strip()
                d_name = str(domestic_raw.get("name") or "").strip()
                if d_ticker and d_name:
                    domestic = {"ticker": d_ticker, "name": d_name}
            picks.append({
                "ticker": ticker,
                "name": str(p.get("name") or "").strip(),
                "description": str(p.get("description") or "").strip(),
                "domestic": domestic,
            })
        cautions_raw = iss.get("cautions")
        cautions = str(cautions_raw).strip() if cautions_raw and str(cautions_raw).strip() else None

        entry: dict = {
            "rank": int(iss.get("rank", len(validated) + 1)),
            "asset": asset,
            "assetType": iss.get("assetType") or "theme",
            "direction": iss.get("direction") or "mixed",
            "signal": str(iss.get("signal") or "").strip(),
            "picks": picks,
            "reason": str(iss.get("reason") or "").strip(),
            "source": str(iss.get("source") or "").strip(),
            "url": iss.get("url") or None,
        }
        if cautions:
            entry["cautions"] = cautions
        validated.append(entry)
    return validated


def analyze_hot_issues(
    candidates: list[tuple[CollectedItem, int]],
    *,
    max_items: int = 60,
) -> list[dict]:
    """해외 소스 기반 오늘 주목할 종목·테마 Top 3 선정.

    candidates: (CollectedItem, score) — 점수 높을수록 우선.
    Tier 오름차순·점수 내림차순 정렬 후 상위 max_items 개를 프롬프트에 포함.
    실패 시 빈 리스트 반환 (파이프라인 중단 없음).
    """
    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    ranked = sorted(
        ((item, score, source_tier_foreign(item.source)) for item, score in candidates),
        key=lambda x: (x[2], -x[1]),
    )[:max_items]

    if not ranked:
        log.warning("hot_issues(foreign): 후보 아이템 없음, 분석 건너뜀")
        return []

    lines: list[str] = []
    for idx, (item, score, tier) in enumerate(ranked, 1):
        display = source_display(item.source)
        lines.append(f"{idx}. [Tier {tier}] [{display}] {item.title} | {item.url}")

    prompt = _PROMPT_SYSTEM + "\n\n---\n\n" + "\n".join(lines)

    try:
        raw = _call_claude(prompt, timeout=60).strip()
        result = _parse_issues(raw)
        log.info("hot_issues(foreign): %d개 이슈 선정", len(result))
        return result
    except Exception as e:
        log.error("hot_issues(foreign) LLM 분석 실패: %s", e)
        return []


def analyze_hot_issues_domestic(
    candidates: list[tuple[CollectedItem, int]],
    *,
    max_items: int = 60,
) -> list[dict]:
    """국내 소스(DART·리서치·한경·매경) 기반 오늘 주목할 종목·테마 Top 3 선정.

    candidates: (CollectedItem, score) — 점수 높을수록 우선.
    실패 시 빈 리스트 반환 (파이프라인 중단 없음).
    """
    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    ranked = sorted(
        ((item, score, source_tier_domestic(item.source)) for item, score in candidates),
        key=lambda x: (x[2], -x[1]),
    )[:max_items]

    if not ranked:
        log.warning("hot_issues(domestic): 후보 아이템 없음, 분석 건너뜀")
        return []

    lines: list[str] = []
    for idx, (item, score, tier) in enumerate(ranked, 1):
        display = source_display(item.source)
        lines.append(f"{idx}. [Tier {tier}] [{display}] {item.title} | {item.url}")

    prompt = _PROMPT_SYSTEM_DOMESTIC + "\n\n---\n\n" + "\n".join(lines)

    try:
        raw = _call_claude(prompt, timeout=60).strip()
        result = _parse_issues(raw)
        log.info("hot_issues(domestic): %d개 이슈 선정", len(result))
        return result
    except Exception as e:
        log.error("hot_issues(domestic) LLM 분석 실패: %s", e)
        return []
