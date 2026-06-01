"""LLM 응답 해시 캐시 (llm_cache 테이블 인터페이스)."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from news_briefing.storage.db import Connection


def hash_content(task: str, input_text: str) -> str:
    h = hashlib.sha256()
    h.update(task.encode("utf-8"))
    h.update(b"\x00")
    h.update(input_text.encode("utf-8"))
    return h.hexdigest()


def cache_get(conn: Connection, task: str, input_text: str) -> str | None:
    key = hash_content(task, input_text)
    r = (
        conn.table("llm_cache")
        .select("output")
        .eq("content_hash", key)
        .limit(1)
        .execute()
    )
    return r.data[0]["output"] if r.data else None


def cache_put(
    conn: Connection, task: str, input_text: str, output: str, model: str
) -> None:
    key = hash_content(task, input_text)
    now = datetime.now(UTC).isoformat()
    conn.table("llm_cache").upsert({
        "content_hash": key,
        "task": task,
        "output": output,
        "model": model,
        "created_at": now,
    }).execute()
