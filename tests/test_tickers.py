from __future__ import annotations

import sqlite3

from news_briefing.storage.db import init_schema
from news_briefing.storage.tickers import (
    TickerRow,
    get_ticker_by_corp,
    get_ticker_by_stock,
    upsert_ticker,
)


def test_roundtrip(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    row = TickerRow(
        stock_code="005930",
        corp_code="00126380",
        corp_name="삼성전자",
        market="KOSPI",
    )
    upsert_ticker(memory_db, row)
    assert get_ticker_by_stock(memory_db, "005930") == row
    assert get_ticker_by_corp(memory_db, "00126380") == row


def test_miss_returns_none(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert get_ticker_by_stock(memory_db, "999999") is None
    assert get_ticker_by_corp(memory_db, "99999999") is None


def test_upsert_overwrites(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_ticker(memory_db, TickerRow("005930", "00126380", "OLD", "KOSPI"))
    upsert_ticker(memory_db, TickerRow("005930", "00126380", "NEW", "KOSPI"))
    row = get_ticker_by_stock(memory_db, "005930")
    assert row is not None
    assert row.corp_name == "NEW"
