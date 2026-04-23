from __future__ import annotations

from pathlib import Path

from news_briefing.collectors.rss import RSS_FEEDS, SOURCE_META, parse_rss_feed


def test_rss_feeds_catalog_has_stock_and_foreign_sources() -> None:
    sources = {f.source for f in RSS_FEEDS}
    assert "rss:hankyung" in sources
    assert "rss:mk" in sources
    assert any("bbc" in f.source for f in RSS_FEEDS)


def test_rss_feeds_catalog_has_google_news_aggregators() -> None:
    sources = {f.source for f in RSS_FEEDS}
    # Week 5a: 카테고리별 Google News aggregator 등록 (국내/해외)
    assert "rss:gnews-politics-kr" in sources
    assert "rss:gnews-society-kr" in sources
    assert "rss:gnews-economy-kr" in sources
    assert "rss:gnews-world-en" in sources


def test_google_news_url_contains_search_and_locale() -> None:
    pol = next(f for f in RSS_FEEDS if f.source == "rss:gnews-politics-kr")
    assert "news.google.com/rss/search" in pol.url
    assert "hl=ko" in pol.url
    assert "gl=KR" in pol.url
    intl = next(f for f in RSS_FEEDS if f.source == "rss:gnews-world-en")
    assert "hl=en" in intl.url
    assert "gl=US" in intl.url


def test_rss_feeds_catalog_has_all_categories() -> None:
    cats = {f.category for f in RSS_FEEDS}
    assert cats == {"stock", "politics", "society", "international", "tech"}


def test_source_meta_contains_all_feeds() -> None:
    for spec in RSS_FEEDS:
        assert spec.source in SOURCE_META
        scope, cat = SOURCE_META[spec.source]
        assert scope == spec.scope
        assert cat == spec.category


def test_parse_preserves_category(fixtures_dir) -> None:
    content = (fixtures_dir / "hankyung.xml").read_text(encoding="utf-8")
    items = parse_rss_feed(content, source_id="rss:hani-politics", category="politics")
    assert items[0].extra.get("category") == "politics"


def test_parse_rss_feed_from_fixture(fixtures_dir: Path) -> None:
    content = (fixtures_dir / "hankyung.xml").read_text(encoding="utf-8")
    items = parse_rss_feed(content, source_id="rss:hankyung")
    assert len(items) == 2
    first = items[0]
    assert first.source == "rss:hankyung"
    assert first.ext_id == "hankyung-2026042200001"
    assert "자사주" in first.title
    assert first.url.startswith("https://")
    assert first.kind == "news"


def test_parse_rss_feed_falls_back_to_link_when_no_guid() -> None:
    feed_no_guid = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>
  <item>
    <title>foo</title>
    <link>https://example.com/a</link>
    <pubDate>Wed, 22 Apr 2026 05:30:00 +0900</pubDate>
  </item>
</channel></rss>"""
    items = parse_rss_feed(feed_no_guid, source_id="rss:x")
    assert len(items) == 1
    assert items[0].ext_id == "https://example.com/a"


def test_google_news_title_strips_publisher_suffix() -> None:
    # Google News item: "제목 - 언론사"
    feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>google news</title>
    <item>
      <title>국회, 추경 편성 논의 - 연합뉴스</title>
      <link>https://news.google.com/rss/articles/abc123</link>
      <guid>gnews-abc123</guid>
      <pubDate>Wed, 23 Apr 2026 10:00:00 +0900</pubDate>
      <source url="https://yonhap.co.kr">연합뉴스</source>
    </item>
  </channel>
</rss>"""
    items = parse_rss_feed(feed, source_id="rss:gnews-politics-kr", category="politics")
    assert len(items) == 1
    assert items[0].title == "국회, 추경 편성 논의"
    assert items[0].extra.get("publisher") == "연합뉴스"
    assert items[0].extra.get("category") == "politics"
