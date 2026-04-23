from __future__ import annotations

from pathlib import Path

from news_briefing.collectors.rss import RSS_FEEDS, SOURCE_META, parse_rss_feed


def test_rss_feeds_catalog_has_stock_and_foreign_sources() -> None:
    sources = {f.source for f in RSS_FEEDS}
    assert "rss:hankyung" in sources
    assert "rss:mk" in sources
    # 해외는 Week 1 시점에 죽어있을 수 있으므로 URL 존재만 체크
    assert any("bbc" in f.source for f in RSS_FEEDS)


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
