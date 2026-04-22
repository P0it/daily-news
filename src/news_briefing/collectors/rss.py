"""RSS 수집기 (feedparser 기반)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from time import mktime

import feedparser
import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RssFeedSpec:
    source: str  # 'rss:hankyung'
    url: str
    scope: str   # 'domestic' | 'foreign'


RSS_FEEDS: list[RssFeedSpec] = [
    RssFeedSpec("rss:hankyung", "https://www.hankyung.com/feed/economy", "domestic"),
    RssFeedSpec("rss:mk", "https://www.mk.co.kr/rss/30000001/", "domestic"),
    RssFeedSpec("rss:bbc-business", "https://feeds.bbci.co.uk/news/business/rss.xml", "foreign"),
    RssFeedSpec("rss:ft-markets", "https://www.ft.com/markets?format=rss", "foreign"),
]


def parse_rss_feed(content: str, source_id: str) -> list[CollectedItem]:
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
        items.append(
            CollectedItem(
                source=source_id,
                ext_id=ext_id,
                kind="news",
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                published_at=published,
                body=entry.get("summary", "").strip(),
            )
        )
    return items


def fetch_rss_feed(spec: RssFeedSpec, *, timeout: int = 15) -> list[CollectedItem]:
    try:
        resp = requests.get(spec.url, timeout=timeout)
        resp.raise_for_status()
        return parse_rss_feed(resp.text, spec.source)
    except Exception as e:
        log.warning("RSS 수집 실패 %s: %s", spec.source, e)
        return []


def fetch_all_rss(feeds: list[RssFeedSpec] | None = None) -> list[CollectedItem]:
    """모든 RSS 피드를 순차 수집 (한 피드 실패해도 다른 피드는 진행)."""
    items: list[CollectedItem] = []
    for spec in feeds if feeds is not None else RSS_FEEDS:
        items.extend(fetch_rss_feed(spec))
    return items
