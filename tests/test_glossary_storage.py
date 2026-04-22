from __future__ import annotations

import sqlite3

from news_briefing.storage.db import init_schema
from news_briefing.storage.glossary import (
    GlossaryEntry,
    get_glossary_entry,
    upsert_glossary_entry,
)


def test_roundtrip(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    entry = GlossaryEntry(
        term_id="self_stock_buy",
        lang="ko",
        short_label="자사주 매수",
        explanation="회사가 자기 주식을 사는 결정이에요.",
        signal_direction="positive",
    )
    upsert_glossary_entry(memory_db, entry)
    got = get_glossary_entry(memory_db, "self_stock_buy", "ko")
    assert got == entry


def test_miss_returns_none(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert get_glossary_entry(memory_db, "unknown", "ko") is None


def test_language_separation(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    ko = GlossaryEntry("self_stock_buy", "ko", "자사주 매수", "한국어", "positive")
    en = GlossaryEntry("self_stock_buy", "en", "Share Buyback", "English", "positive")
    upsert_glossary_entry(memory_db, ko)
    upsert_glossary_entry(memory_db, en)
    assert get_glossary_entry(memory_db, "self_stock_buy", "ko").explanation == "한국어"
    assert get_glossary_entry(memory_db, "self_stock_buy", "en").explanation == "English"


def test_upsert_updates_explanation(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_glossary_entry(
        memory_db,
        GlossaryEntry("x", "ko", "라벨", "구 설명", "neutral"),
    )
    upsert_glossary_entry(
        memory_db,
        GlossaryEntry("x", "ko", "라벨2", "신 설명", "positive"),
    )
    got = get_glossary_entry(memory_db, "x", "ko")
    assert got is not None
    assert got.explanation == "신 설명"
    assert got.short_label == "라벨2"
