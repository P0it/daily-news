"""RSS 수집기 (feedparser 기반).

Week 5a 부터 Google News RSS 를 **1차 aggregator** 로 사용 (한 쿼리 → 여러 언론사).
개별 언론사 RSS 는 품질 보증된 소수(연합·BBC)만 병행.
"""
from __future__ import annotations

import logging
import urllib.parse
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
    source: str                  # 'rss:gnews-politics-kr'
    url: str
    scope: str                   # 'domestic' | 'foreign'
    category: NewsCategory


def _gnews_search(query: str, *, hl: str = "ko", gl: str = "KR") -> str:
    """Google News 검색 RSS URL 생성."""
    q = urllib.parse.quote(query)
    ceid = f"{gl}:{hl}"
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


RSS_FEEDS: list[RssFeedSpec] = [
    # ───── Google News — 카테고리별 aggregator (Week 5a) ─────
    # 한국어: 여러 국내 언론사 aggregate
    RssFeedSpec(
        "rss:gnews-politics-kr",
        _gnews_search("정치 OR 국회 OR 정부"),
        "domestic",
        "politics",
    ),
    RssFeedSpec(
        "rss:gnews-society-kr",
        _gnews_search("사회 OR 사건사고"),
        "domestic",
        "society",
    ),
    RssFeedSpec(
        "rss:gnews-intl-kr",
        _gnews_search("국제 OR 해외"),
        "foreign",
        "international",
    ),
    RssFeedSpec(
        "rss:gnews-tech-kr",
        _gnews_search("IT OR 기술 OR 과학"),
        "domestic",
        "tech",
    ),
    RssFeedSpec(
        "rss:gnews-economy-kr",
        _gnews_search("경제 OR 증권"),
        "domestic",
        "stock",
    ),
    # 영어 (해외 관점 추가 커버리지)
    RssFeedSpec(
        "rss:gnews-world-en",
        _gnews_search("world", hl="en", gl="US"),
        "foreign",
        "international",
    ),
    RssFeedSpec(
        "rss:gnews-business-en",
        _gnews_search("business", hl="en", gl="US"),
        "foreign",
        "stock",
    ),
    RssFeedSpec(
        "rss:gnews-tech-en",
        _gnews_search("technology", hl="en", gl="US"),
        "foreign",
        "tech",
    ),

    # ───── 개별 언론사 RSS — 품질 보증 소수 병행 ─────
    # 경제지 (한국)
    RssFeedSpec("rss:hankyung", "https://www.hankyung.com/feed/economy", "domestic", "stock"),
    RssFeedSpec("rss:mk", "https://www.mk.co.kr/rss/30000001/", "domestic", "stock"),
    # 영어권 공신력
    RssFeedSpec(
        "rss:bbc-business",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "foreign",
        "stock",
    ),
    RssFeedSpec(
        "rss:bbc-world",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "foreign",
        "international",
    ),
    RssFeedSpec("rss:ft-markets", "https://www.ft.com/markets?format=rss", "foreign", "stock"),
    # 연합뉴스 국제 (한국 관점 해외 보도)
    RssFeedSpec(
        "rss:yonhap-intl",
        "https://www.yna.co.kr/rss/international.xml",
        "foreign",
        "international",
    ),
]


# source_id → (scope, category) 조회용
SOURCE_META: dict[str, tuple[str, NewsCategory]] = {
    spec.source: (spec.scope, spec.category) for spec in RSS_FEEDS
}


def _extract_publisher(entry) -> str:
    """Google News entry 에서 언론사명 추출."""
    src = entry.get("source", {})
    if isinstance(src, dict):
        title = src.get("title") or ""
        if title:
            return title
    # fallback: title 끝의 " - 언론사" 패턴
    title = entry.get("title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return ""


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

        # Google News 는 title 이 "제목 - 언론사" 형식 → 언론사 분리
        raw_title = entry.get("title", "").strip()
        publisher = ""
        if source_id.startswith("rss:gnews"):
            publisher = _extract_publisher(entry)
            if publisher and raw_title.endswith(f" - {publisher}"):
                clean_title = raw_title[: -(len(publisher) + 3)].strip()
            else:
                clean_title = raw_title
        else:
            clean_title = raw_title

        extra: dict = {}
        if category:
            extra["category"] = category
        if publisher:
            extra["publisher"] = publisher

        items.append(
            CollectedItem(
                source=source_id,
                ext_id=ext_id,
                kind="news",
                title=clean_title,
                url=entry.get("link", ""),
                published_at=published,
                body=entry.get("summary", "").strip(),
                extra=extra,
            )
        )
    return items


def fetch_rss_feed(spec: RssFeedSpec, *, timeout: int = 15) -> list[CollectedItem]:
    try:
        resp = requests.get(
            spec.url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (news-briefing)"},
        )
        resp.raise_for_status()
        return parse_rss_feed(resp.text, spec.source, spec.category)
    except Exception as e:
        log.warning("RSS 수집 실패 %s: %s", spec.source, e)
        return []


def fetch_all_rss(feeds: list[RssFeedSpec] | None = None) -> list[CollectedItem]:
    """모든 RSS 피드 순차 수집 (한 피드 실패해도 다른 피드는 진행)."""
    items: list[CollectedItem] = []
    for spec in feeds if feeds is not None else RSS_FEEDS:
        items.extend(fetch_rss_feed(spec))
    return items
