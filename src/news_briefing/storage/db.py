"""SQLite 연결 및 스키마 초기화."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    source  TEXT NOT NULL,
    ext_id  TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    PRIMARY KEY (source, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_seen_time ON seen(seen_at);

CREATE TABLE IF NOT EXISTS llm_cache (
    content_hash TEXT PRIMARY KEY,
    task         TEXT NOT NULL,
    output       TEXT NOT NULL,
    model        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS glossary (
    term_id          TEXT NOT NULL,
    lang             TEXT NOT NULL DEFAULT 'ko',
    short_label      TEXT NOT NULL,
    explanation      TEXT NOT NULL,
    signal_direction TEXT,
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (term_id, lang)
);

CREATE TABLE IF NOT EXISTS tickers (
    stock_code TEXT PRIMARY KEY,
    corp_code  TEXT NOT NULL,
    corp_name  TEXT NOT NULL,
    market     TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickers_corp ON tickers(corp_code);

CREATE TABLE IF NOT EXISTS themes (
    theme_id    TEXT PRIMARY KEY,
    name_ko     TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS value_layers (
    layer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id    TEXT NOT NULL REFERENCES themes(theme_id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT NOT NULL,
    UNIQUE (theme_id, name)
);
CREATE INDEX IF NOT EXISTS idx_layers_theme ON value_layers(theme_id);

CREATE TABLE IF NOT EXISTS companies_in_layer (
    layer_id     INTEGER NOT NULL REFERENCES value_layers(layer_id) ON DELETE CASCADE,
    ticker       TEXT NOT NULL,
    company_name TEXT NOT NULL,
    positioning  TEXT,
    verified     INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (layer_id, ticker)
);
CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies_in_layer(ticker);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


@contextmanager
def open_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()
