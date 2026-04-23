from __future__ import annotations

import sqlite3

from news_briefing.storage.db import init_schema
from news_briefing.storage.queries import list_recent_queries, record_query


def test_record_and_list(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    qid = record_query(
        memory_db,
        query="로봇 테마 수혜?",
        answer="에스피지 등이 관련",
        sources=[{"doc_id": "dart:1", "score": 0.87}],
        model="claude-cli",
    )
    assert qid > 0
    records = list_recent_queries(memory_db, limit=10)
    assert len(records) == 1
    assert records[0].query == "로봇 테마 수혜?"
    assert records[0].sources[0]["doc_id"] == "dart:1"


def test_list_desc_order(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    for i in range(3):
        record_query(
            memory_db,
            query=f"q{i}",
            answer="a",
            sources=[],
            model="m",
        )
    records = list_recent_queries(memory_db)
    # 최신순
    assert [r.query for r in records] == ["q2", "q1", "q0"]


def test_limit_applies(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    for i in range(5):
        record_query(memory_db, query=f"q{i}", answer="a", sources=[], model="m")
    records = list_recent_queries(memory_db, limit=2)
    assert len(records) == 2
