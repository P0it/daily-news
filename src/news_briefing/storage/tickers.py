"""corp_code ↔ stock_code ↔ corp_name 매핑 (F18 차트·딥링크 지원)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class TickerRow:
    stock_code: str
    corp_code: str
    corp_name: str
    market: str | None = None


def upsert_ticker(conn: sqlite3.Connection, row: TickerRow) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO tickers(stock_code, corp_code, corp_name, market, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (row.stock_code, row.corp_code, row.corp_name, row.market, now),
    )
    conn.commit()


def get_ticker_by_stock(
    conn: sqlite3.Connection, stock_code: str
) -> TickerRow | None:
    r = conn.execute(
        "SELECT stock_code, corp_code, corp_name, market FROM tickers WHERE stock_code=?",
        (stock_code,),
    ).fetchone()
    if r is None:
        return None
    return TickerRow(
        stock_code=r["stock_code"],
        corp_code=r["corp_code"],
        corp_name=r["corp_name"],
        market=r["market"],
    )


def get_ticker_by_corp(
    conn: sqlite3.Connection, corp_code: str
) -> TickerRow | None:
    r = conn.execute(
        "SELECT stock_code, corp_code, corp_name, market FROM tickers WHERE corp_code=?",
        (corp_code,),
    ).fetchone()
    if r is None:
        return None
    return TickerRow(
        stock_code=r["stock_code"],
        corp_code=r["corp_code"],
        corp_name=r["corp_name"],
        market=r["market"],
    )
