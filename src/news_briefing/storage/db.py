"""PostgreSQL 연결 및 스키마 초기화 (Supabase).

sqlite3.Connection 과 동일한 execute() / commit() / close() 인터페이스를
제공하는 Connection 래퍼를 사용하여 storage 모듈 변경을 최소화한다.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

log = logging.getLogger(__name__)

# Postgres 스키마 — scripts/supabase_schema.sql 과 동기화 유지
_SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS seen (
        source  TEXT NOT NULL,
        ext_id  TEXT NOT NULL,
        seen_at TEXT NOT NULL,
        PRIMARY KEY (source, ext_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_seen_time ON seen(seen_at)",
    """CREATE TABLE IF NOT EXISTS llm_cache (
        content_hash TEXT PRIMARY KEY,
        task         TEXT NOT NULL,
        output       TEXT NOT NULL,
        model        TEXT NOT NULL,
        created_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS glossary (
        term_id          TEXT NOT NULL,
        lang             TEXT NOT NULL DEFAULT 'ko',
        short_label      TEXT NOT NULL,
        explanation      TEXT NOT NULL,
        signal_direction TEXT,
        updated_at       TEXT NOT NULL,
        PRIMARY KEY (term_id, lang)
    )""",
    """CREATE TABLE IF NOT EXISTS tickers (
        stock_code TEXT PRIMARY KEY,
        corp_code  TEXT NOT NULL,
        corp_name  TEXT NOT NULL,
        market     TEXT,
        updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_tickers_corp ON tickers(corp_code)",
    """CREATE TABLE IF NOT EXISTS themes (
        theme_id    TEXT PRIMARY KEY,
        name_ko     TEXT NOT NULL,
        description TEXT,
        updated_at  TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS value_layers (
        layer_id    SERIAL PRIMARY KEY,
        theme_id    TEXT NOT NULL REFERENCES themes(theme_id) ON DELETE CASCADE,
        name        TEXT NOT NULL,
        description TEXT,
        updated_at  TEXT NOT NULL,
        UNIQUE (theme_id, name)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_layers_theme ON value_layers(theme_id)",
    """CREATE TABLE IF NOT EXISTS companies_in_layer (
        layer_id     INTEGER NOT NULL REFERENCES value_layers(layer_id) ON DELETE CASCADE,
        ticker       TEXT NOT NULL,
        company_name TEXT NOT NULL,
        positioning  TEXT,
        verified     INTEGER NOT NULL DEFAULT 0,
        updated_at   TEXT NOT NULL,
        PRIMARY KEY (layer_id, ticker)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies_in_layer(ticker)",
    """CREATE TABLE IF NOT EXISTS embeddings (
        doc_id        TEXT PRIMARY KEY,
        source        TEXT NOT NULL,
        content       TEXT NOT NULL,
        vector        BYTEA NOT NULL,
        dim           INTEGER NOT NULL,
        metadata_json TEXT,
        indexed_at    TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_embeddings_source ON embeddings(source)",
    "CREATE INDEX IF NOT EXISTS idx_embeddings_indexed_at ON embeddings(indexed_at)",
    """CREATE TABLE IF NOT EXISTS rag_queries (
        id           SERIAL PRIMARY KEY,
        query        TEXT NOT NULL,
        answer       TEXT,
        sources_json TEXT,
        model        TEXT,
        created_at   TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_rag_queries_created ON rag_queries(created_at)",
    """CREATE TABLE IF NOT EXISTS briefings (
        date       TEXT PRIMARY KEY,
        data       JSONB NOT NULL,
        created_at TEXT NOT NULL
    )""",
]


class _Cursor:
    """psycopg2 커서의 sqlite3 호환 래퍼."""

    def __init__(self, pg_cursor: Any) -> None:
        self._cur = pg_cursor

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cur.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount


class Connection:
    """psycopg2 연결의 sqlite3 호환 래퍼.

    storage 모듈은 conn.execute() / conn.commit() / conn.close() 만 사용하므로
    이 인터페이스만 노출한다.
    """

    def __init__(self, pg_conn: Any) -> None:
        self._conn = pg_conn

    def execute(self, sql: str, params: tuple = ()) -> _Cursor:
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return _Cursor(cur)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def init_schema(conn: Connection) -> None:
    for stmt in _SCHEMA_STATEMENTS:
        conn.execute(stmt)
    conn.commit()


def connect(database_url: str) -> Connection:
    pg_conn = psycopg2.connect(database_url)
    conn = Connection(pg_conn)
    init_schema(conn)
    return conn


@contextmanager
def open_db(database_url: str) -> Iterator[Connection]:
    conn = connect(database_url)
    try:
        yield conn
    finally:
        conn.close()
