"""LLM 응답 해시 캐시 (llm_cache 테이블 인터페이스)."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime


def hash_content(task: str, input_text: str) -> str:
    h = hashlib.sha256()
    h.update(task.encode("utf-8"))
    h.update(b"\x00")
    h.update(input_text.encode("utf-8"))
    return h.hexdigest()


def cache_get(conn: sqlite3.Connection, task: str, input_text: str) -> str | None:
    key = hash_content(task, input_text)
    row = conn.execute(
        "SELECT output FROM llm_cache WHERE content_hash = ?", (key,)
    ).fetchone()
    return row["output"] if row else None


def cache_put(
    conn: sqlite3.Connection, task: str, input_text: str, output: str, model: str
) -> None:
    key = hash_content(task, input_text)
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO llm_cache(content_hash, task, output, model, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (key, task, output, model, now),
    )
    conn.commit()
