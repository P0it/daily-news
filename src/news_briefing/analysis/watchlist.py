"""관찰 리스트 — 픽이 0인 날 보조 표시.

강한 촉매 픽이 안 나온 scope(국내/해외)에 대해, 그날 점수가 가장 높은 공시
N건을 '관찰' 후보로 추린다. LLM 없이 점수·중복제거만 하는 결정적 로직이며,
픽 품질 게이트와 분리된 read-only 참고 정보다 — 픽으로 승격하지 않는다.

목적: "강한 촉매 없는 날 = 완전 빈 화면" 대신, 사용자가 그래도 지켜볼 만한
공시를 한눈에 보게 한다. 픽(강한 촉매·수혜주 추론)과 명확히 구분한다.
"""

from __future__ import annotations

from news_briefing.analysis.hot_issues import source_display
from news_briefing.analysis.picks import _is_foreign
from news_briefing.collectors.base import CollectedItem

ScoredSignal = tuple[CollectedItem, int, str]

DEFAULT_MIN_SCORE = 75
DEFAULT_N = 6


def select_watchlist(
    scored: list[ScoredSignal],
    *,
    foreign: bool,
    n: int = DEFAULT_N,
    min_score: int = DEFAULT_MIN_SCORE,
    exclude_keys: set[str] | None = None,
) -> list[dict]:
    """scope별 관찰 후보 N건. 같은 기업은 최고 점수만 남긴다.

    - foreign=True 면 해외(EDGAR 등), False 면 국내(DART) 항목만.
    - min_score 미만 제외 (픽 자격 점수와 동일 기준으로 노이즈 차단).
    - exclude_keys: 이미 픽에 들어간 기업 키(소문자) — 중복 표시 방지.
    """
    exclude = exclude_keys or set()
    best: dict[str, ScoredSignal] = {}
    for item, score, direction in scored:
        if score < min_score:
            continue
        if _is_foreign(item) != foreign:
            continue
        # 중복 키: 종목코드 > 회사명 > 제목 순. 와이어 항목은 회사명이 비어
        # ext_id 로 떨어지면 같은 헤드라인이 중복 노출되므로(예: 동일 PR 재배포)
        # 제목을 폴백 키로 써서 같은 사건을 한 번만 남긴다.
        key = (item.company_code or item.company or item.title).strip().lower()
        if key in exclude:
            continue
        existing = best.get(key)
        if existing is None or score > existing[1]:
            best[key] = (item, score, direction)

    ranked = sorted(best.values(), key=lambda t: t[1], reverse=True)[:n]
    return [
        {
            "company": (item.company or item.title[:40]).strip(),
            "code": item.company_code or None,
            "title": item.title.strip(),
            "score": score,
            "direction": direction,
            "source": source_display(item.source),
            "url": item.url or None,
        }
        for item, score, direction in ranked
    ]
