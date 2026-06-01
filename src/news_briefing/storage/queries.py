"""RAG 쿼리 히스토리 (Week 4)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from news_briefing.storage.db import Connection


@dataclass(frozen=True, slots=True)
class QueryRecord:
    id: int | None
    query: str
    answer: str
    sources: list[dict]
    model: str
    created_at: str


def record_query(
    conn: Connection,
    *,
    query: str,
    answer: str,
    sources: list[dict],
    model: str,
) -> int:
    now = datetime.now(UTC).isoformat()
    r = conn.execute(
        "INSERT INTO rag_queries(query, answer, sources_json, model, created_at) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (query, answer, json.dumps(sources, ensure_ascii=False), model, now),
    ).fetchone()
    conn.commit()
    return int(r["id"])


def list_recent_queries(conn: Connection, *, limit: int = 20) -> list[QueryRecord]:
    rows = conn.execute(
        "SELECT id, query, answer, sources_json, model, created_at "
        "FROM rag_queries ORDER BY id DESC LIMIT %s",
        (limit,),
    ).fetchall()
    return [
        QueryRecord(
            id=r["id"],
            query=r["query"],
            answer=r["answer"] or "",
            sources=json.loads(r["sources_json"] or "[]"),
            model=r["model"] or "",
            created_at=r["created_at"],
        )
        for r in rows
    ]
