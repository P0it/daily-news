"""RSS 수집기 (feedparser 기반)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from time import mktime
from typing import Literal

import feedparser
import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

NewsCategory = Literal["stock", "politics", "society", "international", "tech"]


@dataclass(frozen=True, slots=True)
class RssFeedSpec:
    source: str                  # 'rss:hankyung'
    url: str
    scope: str                   # 'domestic' | 'foreign'
    category: NewsCategory       # 'stock' | 'politics' | 'society' | 'international' | 'tech'


RSS_FEEDS: list[RssFeedSpec] = [
    # 경제·주식 (F2, F3)
    RssFeedSpec("rss:hankyung", "https://www.hankyung.com/feed/economy", "domestic", "stock"),
    RssFeedSpec("rss:mk", "https://www.mk.co.kr/rss/30000001/", "domestic", "stock"),
    RssFeedSpec(
        "rss:bbc-business",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "foreign",
        "stock",
    ),
    RssFeedSpec("rss:ft-markets", "https://www.ft.com/markets?format=rss", "foreign", "stock"),
    # 정치 (F27)
    RssFeedSpec(
        "rss:yonhap-politics",
        "https://www.yna.co.kr/rss/politics.xml",
        "domestic",
        "politics",
    ),
    RssFeedSpec(
        "rss:hani-politics", "https://www.hani.co.kr/rss/politics/", "domestic", "politics"
    ),
    # 사회 (F28)
    RssFeedSpec(
        "rss:yonhap-society",
        "https://www.yna.co.kr/rss/society.xml",
        "domestic",
        "society",
    ),
    RssFeedSpec(
        "rss:hani-society", "https://www.hani.co.kr/rss/society/", "domestic", "society"
    ),
    # 국제 (F29) — 내용이 해외 이슈인 경우 scope=foreign (DECISIONS #9 "국제" 필터와 일치)
    RssFeedSpec(
        "rss:yonhap-intl",
        "https://www.yna.co.kr/rss/international.xml",
        "foreign",
        "international",
    ),
    RssFeedSpec(
        "rss:bbc-world",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "foreign",
        "international",
    ),
    # Reuters world RSS: 2025+ 봇 차단 (401). 비활성.
    # IT/과학 (F30)
    RssFeedSpec(
        "rss:zdnet-kr",
        "https://feeds.feedburner.com/zdkorea/AllZDKoreaStoriesFeed",
        "domestic",
        "tech",
    ),
    RssFeedSpec("rss:etnews", "https://rss.etnews.com/20.xml", "domestic", "tech"),
]


# source_id → (scope, category) 조회용 (json_builder 등에서 사용)
SOURCE_META: dict[str, tuple[str, NewsCategory]] = {
    spec.source: (spec.scope, spec.category) for spec in RSS_FEEDS
}


def parse_rss_feed(
    content: str, source_id: str, category: NewsCategory | None = None
) -> list[CollectedItem]:
    parsed = feedparser.parse(content)
    items: list[CollectedItem] = []
    for entry in parsed.entries:
        ext_id = entry.get("id") or entry.get("guid") or entry.get("link", "")
        if not ext_id:
            continue
        published = datetime.now()
        if getattr(entry, "published_parsed", None):
            try:
                published = datetime.fromtimestamp(mktime(entry.published_parsed))
            except Exception:
                pass
        extra: dict = {}
        if category:
            extra["category"] = category
        items.append(
            CollectedItem(
                source=source_id,
                ext_id=ext_id,
                kind="news",
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                published_at=published,
                body=entry.get("summary", "").strip(),
                extra=extra,
            )
        )
    return items


def fetch_rss_feed(spec: RssFeedSpec, *, timeout: int = 15) -> list[CollectedItem]:
    try:
        resp = requests.get(spec.url, timeout=timeout)
        resp.raise_for_status()
        return parse_rss_feed(resp.text, spec.source, spec.category)
    except Exception as e:
        log.warning("RSS 수집 실패 %s: %s", spec.source, e)
        return []


def fetch_all_rss(feeds: list[RssFeedSpec] | None = None) -> list[CollectedItem]:
    """모든 RSS 피드를 순차 수집 (한 피드 실패해도 다른 피드는 진행)."""
    items: list[CollectedItem] = []
    for spec in feeds if feeds is not None else RSS_FEEDS:
        items.extend(fetch_rss_feed(spec))
    return items
