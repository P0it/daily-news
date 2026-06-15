"""보도자료 와이어 수집기 (GlobeNewswire·Business Wire·PR Newswire).

기업은 공식 발표를 기자보다 먼저 와이어에 올린다 → '기사 이전' 1차 소스.
RSS 파싱은 rss.py 의 parse_rss_feed 를 재사용하되, 뉴스 매체가 아닌
공시성 소스이므로 kind='disclosure' 로 재구성해 picks 후보에서 우대한다.
"""
from __future__ import annotations

import logging

import requests

from news_briefing.collectors.base import CollectedItem
from news_briefing.collectors.rss import parse_rss_feed

log = logging.getLogger(__name__)

_TIMEOUT = 15

# (source 접미, RSS URL) — 공개 RSS
_WIRES: list[tuple[str, str]] = [
    (
        "globenewswire",
        "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies",
    ),
    (
        "prnewswire",
        "https://www.prnewswire.com/rss/news-releases-list.rss",
    ),
    (
        "businesswire",
        "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFpRWQ%3D%3D",
    ),
]


def fetch_press_wires() -> list[CollectedItem]:
    """주요 보도자료 와이어 최신 항목 수집 (한 소스 실패해도 나머지 진행)."""
    items: list[CollectedItem] = []
    for suffix, url in _WIRES:
        source_id = f"wire:{suffix}"
        try:
            resp = requests.get(
                url, timeout=_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 (news-briefing)"}
            )
            resp.raise_for_status()
            parsed = parse_rss_feed(resp.text, source_id)
        except Exception as e:
            log.warning("press_wire(%s) 수집 실패 (건너뜀): %s", source_id, e)
            continue

        for it in parsed:
            # parse_rss_feed 는 kind='news' → 공시성 소스로 재구성
            items.append(
                CollectedItem(
                    source=source_id,
                    ext_id=it.ext_id,
                    kind="disclosure",
                    title=it.title,
                    url=it.url,
                    published_at=it.published_at,
                    body=it.body,
                    company=it.company,
                    company_code=it.company_code,
                    extra={**it.extra, "scope": "foreign"},
                )
            )

    log.info("press_wire: %d건 수집", len(items))
    return items
