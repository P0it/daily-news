"""RSS 수집기 (feedparser 기반).

Week 5a 부터 Google News RSS 를 **1차 aggregator** 로 사용 (한 쿼리 → 여러 언론사).
개별 언론사 RSS 는 품질 보증된 소수(연합·BBC)만 병행.
"""
from __future__ import annotations

import html
import logging
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from time import mktime
from typing import Literal

import feedparser
import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

NewsCategory = Literal["stock", "politics", "society", "international", "tech", "ai"]


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

    # ───── AI 탭 (Week 5b) ─────
    # GeekNews (한국 개발자 커뮤니티, AI 섹션)
    RssFeedSpec(
        "rss:geeknews",
        "https://feeds.feedburner.com/geeknews-feed",
        "domestic",
        "ai",
    ),
    # Google News AI 검색 (한국어) — 노이즈 줄이려고 구체적 제품·기술명 위주
    RssFeedSpec(
        "rss:gnews-ai-kr",
        _gnews_search("ChatGPT OR Claude OR Gemini OR 생성형AI OR LLM OR GPT-5"),
        "domestic",
        "ai",
    ),
    # Anthropic 공식 블로그 (Claude 모델 업데이트)
    RssFeedSpec(
        "rss:anthropic",
        "https://www.anthropic.com/rss",
        "foreign",
        "ai",
    ),
    # OpenAI 공식 블로그 (GPT 업데이트)
    RssFeedSpec(
        "rss:openai",
        "https://openai.com/blog/rss.xml",
        "foreign",
        "ai",
    ),
    # Hacker News — AI 관련 (제목에 AI/LLM 등 키워드 많은 상위)
    RssFeedSpec(
        "rss:hn-ai",
        "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude",
        "foreign",
        "ai",
    ),
    # Google News AI 검색 (영어) — 구체적 모델·제품명 위주
    RssFeedSpec(
        "rss:gnews-ai-en",
        _gnews_search(
            'ChatGPT OR Claude OR Gemini OR LLM OR "GPT-5" OR "generative AI"',
            hl="en",
            gl="US",
        ),
        "foreign",
        "ai",
    ),
    # YouTube 채널 RSS — 기본 5개 (Week 2: 사용자가 나중에 data/ai_feeds.json 으로 커스터마이즈)
    RssFeedSpec(
        "rss:yt-fireship",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCsBjURrPoezykLs9EqgamOA",
        "foreign",
        "ai",
    ),
    RssFeedSpec(
        "rss:yt-ai-explained",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCNJ1Ymd5yFuUPtn21xtRbbw",
        "foreign",
        "ai",
    ),
    RssFeedSpec(
        "rss:yt-matthew-berman",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCawZsQWqfGSbCI5yjkdVkTA",
        "foreign",
        "ai",
    ),
    RssFeedSpec(
        "rss:yt-two-minute-papers",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg",
        "foreign",
        "ai",
    ),
    RssFeedSpec(
        "rss:yt-lex-fridman",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCSHZKyawb77ixDdsGog4iWA",
        "foreign",
        "ai",
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
    # fallback: 제목 끝의 " - 언론사" 또는 "\xa0\xa0언론사" 패턴
    title = html.unescape(entry.get("title", "")).replace("\xa0", " ")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    # Google News 한국어: 제목 끝에 여러 공백 후 언론사명
    m = re.search(r"\s{2,}([^\s]+(?:\s[^\s]+){0,2})$", title)
    if m:
        return m.group(1).strip()
    return ""


def _clean_title(raw: str, publisher: str | None = None) -> str:
    """HTML entity 디코드 + nbsp → 공백 + 언론사 suffix 제거."""
    t = html.unescape(raw).replace("\xa0", " ")
    t = re.sub(r"\s{2,}", " ", t).strip()
    if publisher:
        # 다양한 구분자로 끝에 언론사가 붙어있으면 제거
        for suffix in (f" - {publisher}", f" {publisher}"):
            if t.endswith(suffix):
                return t[: -len(suffix)].strip()
    return t


def _clean_body(raw: str) -> str:
    """RSS body: HTML 태그 제거 + entity 디코드 + 공백 정규화."""
    t = re.sub(r"<[^>]+>", " ", raw)  # <p>, <a href=...> 등 제거
    t = html.unescape(t).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


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

        # Google News 는 title 에 "제목 - 언론사" 또는 "제목  언론사" 형식 + &nbsp; 가 섞임
        raw_title = entry.get("title", "").strip()
        publisher = ""
        if source_id.startswith("rss:gnews"):
            publisher = _extract_publisher(entry)
            clean_title = _clean_title(raw_title, publisher)
        else:
            clean_title = _clean_title(raw_title, None)

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
                body=_clean_body(entry.get("summary", "")),
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
