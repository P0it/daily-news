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
