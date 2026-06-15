"""SEC EDGAR 13F·13D·13G 수집기 — 기관·구루 보유 변동 + 행동주의 지분 취득.

edgar.py 의 8-K/Form4 와 같은 getcurrent Atom 패턴을 재사용하되,
보유·지분 신고는 lookback·cap 의미가 달라 별도 모듈로 분리한다.

- SC 13D: 5%+ 취득 + '경영 참여 의도' → 행동주의 신호 (강)
- SC 13G: 5%+ 취득 but 단순 투자(패시브) → 중
- 13F-HR: 기관 분기 보유 내역 → 신규 편입 참고
"""
from __future__ import annotations

import logging

import requests

from news_briefing.collectors.base import CollectedItem
from news_briefing.collectors.edgar import EDGAR_BROWSE_URL, parse_edgar_atom

log = logging.getLogger(__name__)

_TIMEOUT = 15

# (EDGAR type 파라미터, source 접두 표시용 form_type, 기본 점수)
_FORMS: list[tuple[str, int]] = [
    ("SC 13D", 85),
    ("SC 13G", 70),
    ("13F-HR", 65),
]


def _fetch_form(
    form_type: str, pre_scored: int, *, user_agent: str, count: int
) -> list[CollectedItem]:
    """단일 form_type 의 최신 공시를 getcurrent Atom 으로 수집."""
    try:
        resp = requests.get(
            EDGAR_BROWSE_URL,
            params={
                "action": "getcurrent",
                "type": form_type,
                "dateb": "",
                "owner": "include",
                "count": count,
                "output": "atom",
            },
            headers={"User-Agent": user_agent, "Accept": "application/atom+xml"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        parsed = parse_edgar_atom(resp.text, form_type)
    except Exception as e:
        log.error("EDGAR %s 수집 실패: %s", form_type, e)
        return []

    # parse_edgar_atom 은 source='edgar' 로 만들므로, 별도 소스명·scope·pre_scored 로 재구성
    items: list[CollectedItem] = []
    for it in parsed:
        items.append(
            CollectedItem(
                source="edgar_13f",
                ext_id=it.ext_id,
                kind="disclosure",
                title=it.title,
                url=it.url,
                published_at=it.published_at,
                body=it.body,
                company=it.company,
                company_code=it.company_code,
                extra={
                    **it.extra,
                    "scope": "foreign",
                    "pre_scored": pre_scored,
                },
            )
        )
    return items


def fetch_institutional_13f(user_agent: str, *, count: int = 40) -> list[CollectedItem]:
    """13D·13G·13F-HR 최신 공시 수집 (한 폼 실패해도 나머지 진행).

    user_agent 가 없으면 빈 리스트 (SEC 정책상 UA 필수).
    """
    if not user_agent:
        log.warning("EDGAR User-Agent 없음, 13F 계열 수집 스킵")
        return []

    items: list[CollectedItem] = []
    for form_type, pre_scored in _FORMS:
        items.extend(_fetch_form(form_type, pre_scored, user_agent=user_agent, count=count))
    log.info("institutional_13f: %d건 수집", len(items))
    return items
