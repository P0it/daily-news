"""corp_code ↔ stock_code ↔ corp_name 매핑 (F18 차트·딥링크 지원)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from news_briefing.storage.db import Connection


@dataclass(frozen=True, slots=True)
class TickerRow:
    stock_code: str
    corp_code: str
    corp_name: str
    market: str | None = None


def upsert_ticker(conn: Connection, row: TickerRow) -> None:
    now = datetime.now(UTC).isoformat()
    conn.table("tickers").upsert({
        "stock_code": row.stock_code,
        "corp_code": row.corp_code,
        "corp_name": row.corp_name,
        "market": row.market,
        "updated_at": now,
    }).execute()


def get_ticker_by_stock(conn: Connection, stock_code: str) -> TickerRow | None:
    r = (
        conn.table("tickers")
        .select("stock_code,corp_code,corp_name,market")
        .eq("stock_code", stock_code)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    d = r.data[0]
    return TickerRow(
        stock_code=d["stock_code"],
        corp_code=d["corp_code"],
        corp_name=d["corp_name"],
        market=d["market"],
    )


def get_ticker_by_corp(conn: Connection, corp_code: str) -> TickerRow | None:
    r = (
        conn.table("tickers")
        .select("stock_code,corp_code,corp_name,market")
        .eq("corp_code", corp_code)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    d = r.data[0]
    return TickerRow(
        stock_code=d["stock_code"],
        corp_code=d["corp_code"],
        corp_name=d["corp_name"],
        market=d["market"],
    )
