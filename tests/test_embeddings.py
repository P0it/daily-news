from __future__ import annotations

import sqlite3

import numpy as np

from news_briefing.storage.db import init_schema
from news_briefing.storage.embeddings import (
    EmbeddingRow,
    count_embeddings,
    get_embedding,
    has_embedding,
    similarity_search,
    upsert_embedding,
)


def _row(doc_id: str, source: str, content: str, vec: list[float]) -> EmbeddingRow:
    return EmbeddingRow(
        doc_id=doc_id,
        source=source,
        content=content,
        vector=np.array(vec, dtype=np.float32),
        metadata={"doc": doc_id},
    )


def test_roundtrip(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    row = _row("d1", "dart", "테스트 본문", [1.0, 0.0, 0.0])
    upsert_embedding(memory_db, row)
    got = get_embedding(memory_db, "d1")
    assert got is not None
    assert got.content == "테스트 본문"
    np.testing.assert_allclose(got.vector, [1.0, 0.0, 0.0])


def test_has_embedding(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert has_embedding(memory_db, "x") is False
    upsert_embedding(memory_db, _row("x", "dart", "c", [1.0]))
    assert has_embedding(memory_db, "x") is True


def test_similarity_search_returns_closest_first(
    memory_db: sqlite3.Connection,
) -> None:
    init_schema(memory_db)
    upsert_embedding(memory_db, _row("a", "dart", "가까움", [1.0, 0.0]))
    upsert_embedding(memory_db, _row("b", "dart", "중간", [0.7, 0.7]))
    upsert_embedding(memory_db, _row("c", "dart", "멀음", [0.0, 1.0]))
    q = np.array([1.0, 0.0], dtype=np.float32)
    result = similarity_search(memory_db, q, top_k=3)
    doc_ids = [r.doc_id for r, _ in result]
    assert doc_ids == ["a", "b", "c"]
    # 첫 번째는 거의 1.0 유사도
    assert result[0][1] > 0.99


def test_empty_db_returns_empty_results(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    q = np.array([1.0, 0.0], dtype=np.float32)
    assert similarity_search(memory_db, q) == []


def test_zero_query_vector_returns_empty(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_embedding(memory_db, _row("a", "dart", "x", [1.0, 0.0]))
    q = np.array([0.0, 0.0], dtype=np.float32)
    assert similarity_search(memory_db, q) == []


def test_count(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert count_embeddings(memory_db) == 0
    upsert_embedding(memory_db, _row("a", "dart", "x", [1.0]))
    upsert_embedding(memory_db, _row("b", "dart", "y", [1.0]))
    assert count_embeddings(memory_db) == 2
