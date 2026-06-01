"""LLM 기반 '오늘의 핵심 이슈' 분석 (해외 공신력 소스 우선).

키워드 빈도 카운팅 방식을 대체한다. Claude CLI 에게 오늘 수집된 아이템 목록을
출처 티어와 함께 전달하고, 해외 투자자 관점에서 가장 중요한 이슈 3개를 선정하게 한다.
"""
from __future__ import annotations

import json
import logging

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

# 소스 ID → 티어 (낮을수록 우선)
_TIER_MAP: dict[str, int] = {
    "edgar":              1,
    "rss:ft-markets":     1,
    "rss:bbc-business":   1,
    "rss:bbc-world":      1,
    "rss:gnews-world-en": 2,
    "rss:gnews-business-en": 2,
    "rss:gnews-tech-en":  2,
    "rss:yonhap-intl":    2,
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
너는 해외 주식 투자자를 위한 경제 뉴스 편집장이다.
아래에 오늘 수집된 기사·공시 목록이 있다. 각 항목에는 [Tier N]과 출처명이 표시되어 있다.

이 목록에서 해외(미국·글로벌) 주식 투자자에게 오늘 가장 중요한 이슈 3개를 선정하라.

선정 기준 (우선순위 순):
1. Tier 1 소스(SEC EDGAR·Financial Times·BBC) 발 단독 보도 또는 공식 발표
2. 연준(Fed)·미국 정부·중앙은행 정책 발표
3. 미국 증시·달러·금리·원자재에 직접 영향을 주는 기업 실적·M&A·규제 뉴스
4. 동일 사건 반복 기사보다 새로운 사건 우선

출력 규칙:
- JSON 배열만 반환. 마크다운 코드 블록, 설명 텍스트 없이 배열 그대로 출력.
- 배열 길이는 정확히 3.
- 각 원소 형식:
  {"rank": 숫자, "title": "한국어 제목 30자 이내", "reason": "왜 해외 투자자에게 중요한지 1~2문장 '~요'체", "source": "언론사명", "url": "원문 URL 또는 null"}
"""


def analyze_hot_issues(
    candidates: list[tuple[CollectedItem, int]],
    *,
    max_items: int = 60,
) -> list[dict]:
    """수집 아이템에서 LLM으로 오늘의 핵심 이슈 Top 3 선정.

    candidates: (CollectedItem, score) — 점수가 높을수록 우선 노출.
    Tier 1/2 소스 우선 정렬 후 상위 max_items 개를 LLM 프롬프트에 포함.
    실패 시 빈 리스트 반환 (파이프라인 중단 없음).
    """
    # 내부 함수 재사용 — 임포트는 런타임에 (순환 참조 방지)
    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    # 티어 오름차순, 점수 내림차순 정렬
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
        # markdown fence 제거
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.splitlines()[:-1])
        raw = raw.strip()

        issues: list[dict] = json.loads(raw)
        validated: list[dict] = []
        for iss in issues[:3]:
            title = str(iss.get("title", "")).strip()
            if not title:
                continue
            validated.append({
                "rank": int(iss.get("rank", len(validated) + 1)),
                "title": title,
                "reason": str(iss.get("reason", "")).strip(),
                "source": str(iss.get("source", "")).strip(),
                "url": iss.get("url") or None,
            })
        log.info("hot_issues: %d개 이슈 선정", len(validated))
        return validated
    except Exception as e:
        log.error("hot_issues LLM 분석 실패: %s", e)
        return []
