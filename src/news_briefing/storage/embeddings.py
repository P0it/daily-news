"""벡터 임베딩 CRUD + 코사인 유사도 검색 (Week 4).

Chroma 대신 SQLite BLOB + numpy — 개인 스케일에 충분.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np


@dataclass(frozen=True, slots=True)
class EmbeddingRow:
    doc_id: str
    source: str
    content: str
    vector: np.ndarray
    metadata: dict


def _serialize(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()


def _deserialize(b: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32, count=dim).copy()


def upsert_embedding(conn: sqlite3.Connection, row: EmbeddingRow) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO embeddings"
        "(doc_id, source, content, vector, dim, metadata_json, indexed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            row.doc_id,
            row.source,
            row.content,
            _serialize(row.vector),
            row.vector.shape[0],
            json.dumps(row.metadata, ensure_ascii=False),
            now,
        ),
    )
    conn.commit()


def has_embedding(conn: sqlite3.Connection, doc_id: str) -> bool:
    r = conn.execute(
        "SELECT 1 FROM embeddings WHERE doc_id=?", (doc_id,)
    ).fetchone()
    return r is not None


def get_embedding(conn: sqlite3.Connection, doc_id: str) -> EmbeddingRow | None:
    r = conn.execute(
        "SELECT doc_id, source, content, vector, dim, metadata_json "
        "FROM embeddings WHERE doc_id=?",
        (doc_id,),
    ).fetchone()
    if r is None:
        return None
    return EmbeddingRow(
        doc_id=r["doc_id"],
        source=r["source"],
        content=r["content"],
        vector=_deserialize(r["vector"], r["dim"]),
        metadata=json.loads(r["metadata_json"] or "{}"),
    )


def similarity_search(
    conn: sqlite3.Connection, query_vector: np.ndarray, *, top_k: int = 5
) -> list[tuple[EmbeddingRow, float]]:
    rows = conn.execute(
        "SELECT doc_id, source, content, vector, dim, metadata_json FROM embeddings"
    ).fetchall()
    if not rows:
        return []

    q = query_vector.astype(np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []
    q = q / q_norm

    scored: list[tuple[EmbeddingRow, float]] = []
    for r in rows:
        v = _deserialize(r["vector"], r["dim"])
        n = np.linalg.norm(v)
        if n == 0:
            continue
        sim = float(np.dot(q, v / n))
        scored.append(
            (
                EmbeddingRow(
                    doc_id=r["doc_id"],
                    source=r["source"],
                    content=r["content"],
                    vector=v,
                    metadata=json.loads(r["metadata_json"] or "{}"),
                ),
                sim,
            )
        )
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def count_embeddings(conn: sqlite3.Connection) -> int:
    r = conn.execute("SELECT COUNT(*) AS n FROM embeddings").fetchone()
    return int(r["n"])
