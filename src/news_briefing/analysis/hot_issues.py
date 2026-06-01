"""LLM 기반 '오늘의 주목 종목/테마' 분석 (해외 공신력 소스 우선).

뉴스 기사를 단순 나열하는 대신, 해외 투자자 관점에서 오늘 주목할 종목·테마를
먼저 제시하고 그 근거가 된 기사/공시를 함께 반환한다.
"""
from __future__ import annotations

import json
import logging

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

# 소스 ID → 티어 (낮을수록 우선)
_TIER_MAP: dict[str, int] = {
    "edgar":                 1,
    "rss:ft-markets":        1,
    "rss:bbc-business":      1,
    "rss:bbc-world":         1,
    "rss:gnews-world-en":    2,
    "rss:gnews-business-en": 2,
    "rss:gnews-tech-en":     2,
    "rss:yonhap-intl":       2,
}
_DEFAULT_TIER = 3

# 소스 ID → 표시용 언론사명
_DISPLAY_MAP: dict[str, str] = {
    "edgar":                 "SEC EDGAR",
    "dart":                  "DART",
    "rss:ft-markets":        "Financial Times",
    "rss:bbc-business":      "BBC Business",
    "rss:bbc-world":         "BBC World",
    "rss:gnews-world-en":    "Google News (World)",
    "rss:gnews-business-en": "Google News (Business)",
    "rss:gnews-tech-en":     "Google News (Tech)",
    "rss:yonhap-intl":       "연합뉴스 국제",
    "rss:hankyung":          "한국경제",
    "rss:mk":                "매일경제",
}


def source_tier(source: str) -> int:
    return _TIER_MAP.get(source, _DEFAULT_TIER)


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

출력 규칙:
- JSON 배열만 반환. 마크다운 코드블록·설명 텍스트 없이 배열 그대로.
- 배열 길이 정확히 3.
- 각 원소:
  {
    "rank": 숫자,
    "asset": "투자 대상 이름. 종목이면 티커(예: NVDA·MSFT), 테마면 짧은 한국어(예: 에너지·반도체), 매크로면 자산명(예: 달러·WTI원유). 절대 뉴스 제목을 그대로 쓰지 말 것.",
    "assetType": "stock" | "theme" | "macro",
    "direction": "positive" | "negative" | "mixed",
    "signal": "핵심 시그널 15자 이내 (예: 가이던스 상향, 금리 동결, 규제 리스크)",
    "tickers": ["관련 미국 주식·ETF 티커 최대 4개. 예: NVDA, SMH, TSM. 없으면 빈 배열 []"],
    "reason": "왜 오늘 이 자산에 주목해야 하는지 2~3문장, '~요'체, 구체적 수치 포함",
    "source": "출처 언론사명",
    "url": "원문 URL 또는 null"
  }

중요: asset 필드에 뉴스 제목이나 긴 문장을 쓰면 안 됨. 반드시 투자 대상 이름(티커 또는 짧은 테마명)만 기입.
"""


def analyze_hot_issues(
    candidates: list[tuple[CollectedItem, int]],
    *,
    max_items: int = 60,
) -> list[dict]:
    """수집 아이템에서 LLM으로 오늘 주목할 종목·테마 Top 3 선정.

    candidates: (CollectedItem, score) — 점수 높을수록 우선.
    Tier 오름차순·점수 내림차순 정렬 후 상위 max_items 개를 프롬프트에 포함.
    실패 시 빈 리스트 반환 (파이프라인 중단 없음).
    """
    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    ranked = sorted(
        ((item, score, source_tier(item.source)) for item, score in candidates),
        key=lambda x: (x[2], -x[1]),
    )[:max_items]

    if not ranked:
        log.warning("hot_issues: 후보 아이템 없음, 분석 건너뜀")
        return []

    lines: list[str] = []
    for idx, (item, score, tier) in enumerate(ranked, 1):
        display = source_display(item.source)
        lines.append(f"{idx}. [Tier {tier}] [{display}] {item.title} | {item.url}")

    prompt = _PROMPT_SYSTEM + "\n\n---\n\n" + "\n".join(lines)

    try:
        raw = _call_claude(prompt, timeout=60).strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.splitlines()[:-1])
        raw = raw.strip()

        issues: list[dict] = json.loads(raw)
        validated: list[dict] = []
        for iss in issues[:3]:
            # LLM이 title 또는 asset 중 하나를 쓸 수 있음 — 둘 다 수용
            asset = str(iss.get("asset") or iss.get("title") or "").strip()
            if not asset:
                continue
            raw_tickers = iss.get("tickers") or []
            tickers = [str(t).strip().upper() for t in raw_tickers if str(t).strip()][:4]
            validated.append({
                "rank": int(iss.get("rank", len(validated) + 1)),
                "asset": asset,
                "assetType": iss.get("assetType") or "theme",
                "direction": iss.get("direction") or "mixed",
                "signal": str(iss.get("signal") or "").strip(),
                "tickers": tickers,
                "reason": str(iss.get("reason") or "").strip(),
                "source": str(iss.get("source") or "").strip(),
                "url": iss.get("url") or None,
            })
        log.info("hot_issues: %d개 이슈 선정", len(validated))
        return validated
    except Exception as e:
        log.error("hot_issues LLM 분석 실패: %s", e)
        return []
