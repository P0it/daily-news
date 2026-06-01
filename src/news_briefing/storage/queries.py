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
    r = conn.table("rag_queries").insert({
        "query": query,
        "answer": answer,
        "sources_json": json.dumps(sources, ensure_ascii=False),
        "model": model,
        "created_at": now,
    }).execute()
    return int(r.data[0]["id"])


def list_recent_queries(conn: Connection, *, limit: int = 20) -> list[QueryRecord]:
    r = (
        conn.table("rag_queries")
        .select("id,query,answer,sources_json,model,created_at")
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
    return [
        QueryRecord(
            id=d["id"],
            query=d["query"],
            answer=d["answer"] or "",
            sources=json.loads(d["sources_json"] or "[]"),
            model=d["model"] or "",
            created_at=d["created_at"],
        )
        for d in r.data
    ]
