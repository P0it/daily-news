"""벡터 임베딩 CRUD + 코사인 유사도 검색 (Week 4).

REST API 경유로 BYTEA 를 base64 인코딩해서 저장/복원한다.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from news_briefing.storage.db import Connection


@dataclass(frozen=True, slots=True)
class EmbeddingRow:
    doc_id: str
    source: str
    content: str
    vector: np.ndarray
    metadata: dict


def _to_b64(v: np.ndarray) -> str:
    return base64.b64encode(v.astype(np.float32).tobytes()).decode("ascii")


def _from_b64(s: str, dim: int) -> np.ndarray:
    # PostgREST 는 BYTEA 를 hex(\x...) 또는 base64 로 반환할 수 있다
    if isinstance(s, str) and s.startswith("\\x"):
        raw = bytes.fromhex(s[2:])
    else:
        raw = base64.b64decode(s)
    return np.frombuffer(raw, dtype=np.float32, count=dim).copy()


def upsert_embedding(conn: Connection, row: EmbeddingRow) -> None:
    now = datetime.now(UTC).isoformat()
    conn.table("embeddings").upsert({
        "doc_id": row.doc_id,
        "source": row.source,
        "content": row.content,
        "vector": _to_b64(row.vector),
        "dim": row.vector.shape[0],
        "metadata_json": json.dumps(row.metadata, ensure_ascii=False),
        "indexed_at": now,
    }).execute()


def has_embedding(conn: Connection, doc_id: str) -> bool:
    r = conn.table("embeddings").select("doc_id").eq("doc_id", doc_id).limit(1).execute()
    return len(r.data) > 0


def get_embedding(conn: Connection, doc_id: str) -> EmbeddingRow | None:
    r = (
        conn.table("embeddings")
        .select("doc_id,source,content,vector,dim,metadata_json")
        .eq("doc_id", doc_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    d = r.data[0]
    return EmbeddingRow(
        doc_id=d["doc_id"],
        source=d["source"],
        content=d["content"],
        vector=_from_b64(d["vector"], d["dim"]),
        metadata=json.loads(d["metadata_json"] or "{}"),
    )


def similarity_search(
    conn: Connection, query_vector: np.ndarray, *, top_k: int = 5
) -> list[tuple[EmbeddingRow, float]]:
    r = conn.table("embeddings").select("doc_id,source,content,vector,dim,metadata_json").execute()
    if not r.data:
        return []

    q = query_vector.astype(np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []
    q = q / q_norm

    scored: list[tuple[EmbeddingRow, float]] = []
    for d in r.data:
        v = _from_b64(d["vector"], d["dim"])
        n = np.linalg.norm(v)
        if n == 0:
            continue
        sim = float(np.dot(q, v / n))
        scored.append((
            EmbeddingRow(
                doc_id=d["doc_id"],
                source=d["source"],
                content=d["content"],
                vector=v,
                metadata=json.loads(d["metadata_json"] or "{}"),
            ),
            sim,
        ))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def count_embeddings(conn: Connection) -> int:
    r = conn.table("embeddings").select("doc_id", count="exact").execute()
    return r.count or 0
