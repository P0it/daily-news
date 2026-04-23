# Week 4: RAG 분석 + 주간 에세이 + 테마 배너 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ROADMAP 최종 주차. (1) 지난 브리핑 JSON 을 벡터 인덱싱하여 자유 질의에 출처 포함 답변을 주는 **RAG 엔진**, (2) 주간 리포트 **LLM 에세이 고도화** + 트렌드 테마 배너 데이터, (3) 경제 탭 **"이번 주 주목 테마" 배너 UI** (F12), (4) **쿼리 히스토리** 저장.

**Architecture:** 벡터 스토어는 **SQLite `embeddings` 테이블 + BLOB 벡터 + numpy 코사인 유사도** — Chroma 대신 이식성·의존성 최소화 (개인 스케일, 수백~수천 문서). 임베딩은 **Ollama `nomic-embed-text` 로컬 호출** (P2 — API 과금 없음). Ollama 미설치 시 키워드 fallback. 답변 생성은 기존 `claude CLI` 재사용 + RAG 프롬프트. Weekly 에세이는 Week 3 `weekly.py` 의 `render_weekly_html` 을 LLM essay 섹션으로 확장.

**Tech Stack:** 기존 + `numpy` (≈20MB, 코사인 계산용). Chroma/FAISS 미사용.

---

## File Structure (Week 4 결과물)

### 백엔드

| 파일 | 책임 |
|------|------|
| `src/news_briefing/storage/db.py` (수정) | `embeddings` + `rag_queries` 테이블 |
| `src/news_briefing/storage/embeddings.py` | 벡터 CRUD + 코사인 검색 |
| `src/news_briefing/storage/queries.py` | 쿼리 히스토리 |
| `src/news_briefing/analysis/embed.py` | Ollama embedding 호출 + fallback |
| `src/news_briefing/analysis/rag.py` | 인덱싱 파이프라인 + 질의 |
| `src/news_briefing/analysis/trends.py` (수정) | 브리핑 JSON 에서 title 이벤트 추출 헬퍼 |
| `src/news_briefing/delivery/weekly.py` (수정) | LLM 에세이 섹션 + trending_themes |
| `src/news_briefing/orchestrator.py` (수정) | morning 시 신규 문서 인덱싱 + economy.themeBanner 생성 |
| `src/news_briefing/delivery/json_builder.py` (수정) | `tabs.economy.themeBanner` 채움 |
| `src/news_briefing/cli.py` (수정) | `ask <query>` 서브커맨드 |

### 프론트엔드

| 파일 | 책임 |
|------|------|
| `frontend/src/components/ThemeBanner.tsx` | 경제 탭 상단 "이번 주 주목 테마" 배너 |
| `frontend/src/app/page.tsx` (수정) | 경제 탭에 ThemeBanner 렌더 |
| `frontend/src/lib/types.ts` (수정) | `ThemeBanner` 인터페이스 사용 확인 |

### 테스트

| 파일 | 책임 |
|------|------|
| `tests/test_embeddings.py` | 벡터 CRUD + 코사인 |
| `tests/test_embed.py` | Ollama HTTP mock |
| `tests/test_rag.py` | 인덱싱 + 질의 mock |
| `tests/test_weekly_essay.py` | LLM 에세이 mock |
| `tests/test_queries.py` | 쿼리 히스토리 |

---

## Task 1: `embeddings` + `rag_queries` 테이블 스키마

**Files:**
- Modify: `src/news_briefing/storage/db.py`
- Create: `src/news_briefing/storage/embeddings.py`
- Create: `src/news_briefing/storage/queries.py`
- Create: `tests/test_embeddings.py`
- Create: `tests/test_queries.py`

- [ ] **Step 1: Extend _SCHEMA**

```sql
CREATE TABLE IF NOT EXISTS embeddings (
    doc_id        TEXT PRIMARY KEY,       -- 'dart:20260422000001' 같은 고유 ID
    source        TEXT NOT NULL,          -- 'dart', 'edgar', 'rss:hankyung' 등
    content       TEXT NOT NULL,          -- 원문 (인덱싱 대상 텍스트)
    vector        BLOB NOT NULL,          -- numpy float32 array bytes
    dim           INTEGER NOT NULL,       -- 벡터 차원
    metadata_json TEXT,                   -- {"date":"2026-04-22","company":"삼성전자"}
    indexed_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_embeddings_source ON embeddings(source);
CREATE INDEX IF NOT EXISTS idx_embeddings_indexed_at ON embeddings(indexed_at);

CREATE TABLE IF NOT EXISTS rag_queries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query         TEXT NOT NULL,
    answer        TEXT,
    sources_json  TEXT,                   -- [{"doc_id":"...","score":0.87}, ...]
    model         TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rag_queries_created ON rag_queries(created_at);
```

- [ ] **Step 2: storage/embeddings.py**

```python
# src/news_briefing/storage/embeddings.py
"""벡터 임베딩 CRUD + 코사인 유사도 검색."""
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
    r = conn.execute("SELECT 1 FROM embeddings WHERE doc_id=?", (doc_id,)).fetchone()
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
    """전체 테이블 스캔 + 코사인. 개인 스케일(≤수만 건)에 충분."""
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
```

- [ ] **Step 3: storage/queries.py**

```python
# src/news_briefing/storage/queries.py
"""RAG 쿼리 히스토리."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class QueryRecord:
    id: int | None
    query: str
    answer: str
    sources: list[dict]
    model: str
    created_at: str


def record_query(
    conn: sqlite3.Connection,
    *,
    query: str,
    answer: str,
    sources: list[dict],
    model: str,
) -> int:
    now = datetime.now(UTC).isoformat()
    r = conn.execute(
        "INSERT INTO rag_queries(query, answer, sources_json, model, created_at) "
        "VALUES (?, ?, ?, ?, ?) RETURNING id",
        (query, answer, json.dumps(sources, ensure_ascii=False), model, now),
    ).fetchone()
    conn.commit()
    return int(r["id"])


def list_recent_queries(
    conn: sqlite3.Connection, *, limit: int = 20
) -> list[QueryRecord]:
    rows = conn.execute(
        "SELECT id, query, answer, sources_json, model, created_at "
        "FROM rag_queries ORDER BY id DESC LIMIT ?",
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
```

- [ ] **Step 4: Test — embeddings CRUD + similarity**

```python
# tests/test_embeddings.py
from __future__ import annotations

import sqlite3

import numpy as np

from news_briefing.storage.db import init_schema
from news_briefing.storage.embeddings import (
    EmbeddingRow,
    count_embeddings,
    get_embedding,
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


def test_count(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert count_embeddings(memory_db) == 0
    upsert_embedding(memory_db, _row("a", "dart", "x", [1.0]))
    upsert_embedding(memory_db, _row("b", "dart", "y", [1.0]))
    assert count_embeddings(memory_db) == 2
```

- [ ] **Step 5: Test — queries history**

```python
# tests/test_queries.py
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
```

- [ ] **Step 6: pyproject.toml 에 numpy 추가 + install**

```toml
dependencies = [
    "feedparser>=6.0.11",
    "python-dotenv>=1.0.1",
    "requests>=2.32.0",
    "numpy>=2.0.0",
]
```

```bash
uv pip install --python .venv/Scripts/python.exe numpy
```

- [ ] **Step 7: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_embeddings.py tests/test_queries.py -v
git add pyproject.toml src/news_briefing/storage/db.py src/news_briefing/storage/embeddings.py src/news_briefing/storage/queries.py tests/test_embeddings.py tests/test_queries.py
git commit -m "feat(storage): embeddings + rag_queries tables with SQLite+numpy cosine"
```

---

## Task 2: Ollama embedding 클라이언트

**Files:**
- Create: `src/news_briefing/analysis/embed.py`
- Create: `tests/test_embed.py`
- Modify: `src/news_briefing/config.py` (add `ollama_embed_model`)

- [ ] **Step 1: Config**

```python
# Config 에 추가:
ollama_embed_model: str  # 기본 'nomic-embed-text'

# load_config:
ollama_embed_model=os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
```

`.env.example` 에 추가:
```
OLLAMA_EMBED_MODEL=nomic-embed-text
```

- [ ] **Step 2: embed.py**

```python
# src/news_briefing/analysis/embed.py
"""임베딩 클라이언트 — Ollama HTTP API 우선, 실패 시 키워드 fallback.

P2 원칙 준수: OpenAI embedding API 미사용.
"""
from __future__ import annotations

import hashlib
import logging

import numpy as np
import requests

log = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/embeddings"


def embed_ollama(text: str, *, model: str, timeout: int = 30) -> np.ndarray | None:
    """Ollama embedding API 호출. 실패 시 None."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": text},
            timeout=timeout,
        )
        if resp.status_code != 200:
            log.warning("ollama embed status=%s", resp.status_code)
            return None
        data = resp.json()
        vec = data.get("embedding")
        if not vec:
            return None
        return np.array(vec, dtype=np.float32)
    except Exception as e:
        log.warning("ollama embed 예외: %s", e)
        return None


_HASH_DIM = 256


def embed_hash(text: str) -> np.ndarray:
    """Fallback — 결정적 해시 기반 pseudo-embedding. 유사도 품질 낮지만 파이프라인 동작 보장."""
    vec = np.zeros(_HASH_DIM, dtype=np.float32)
    tokens = text.split()
    for tok in tokens:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % _HASH_DIM
        vec[idx] += 1.0
    n = np.linalg.norm(vec)
    return vec / n if n > 0 else vec


def embed(text: str, *, model: str) -> np.ndarray:
    """Ollama 시도 후 실패 시 hash fallback. 빈 문자열은 zero vector."""
    if not text.strip():
        return np.zeros(_HASH_DIM, dtype=np.float32)
    v = embed_ollama(text, model=model)
    if v is not None:
        return v
    return embed_hash(text)
```

- [ ] **Step 3: Test (mock requests)**

```python
# tests/test_embed.py
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from news_briefing.analysis.embed import embed, embed_hash, embed_ollama


def test_embed_ollama_success(mocker) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    mocker.patch(
        "news_briefing.analysis.embed.requests.post", return_value=mock_resp
    )
    v = embed_ollama("hello", model="nomic-embed-text")
    assert v is not None
    np.testing.assert_allclose(v, [0.1, 0.2, 0.3])


def test_embed_ollama_failure_returns_none(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.embed.requests.post",
        side_effect=Exception("conn refused"),
    )
    assert embed_ollama("x", model="any") is None


def test_embed_hash_is_deterministic() -> None:
    a = embed_hash("삼성전자 자사주 매수")
    b = embed_hash("삼성전자 자사주 매수")
    np.testing.assert_allclose(a, b)


def test_embed_hash_different_inputs_different_vectors() -> None:
    a = embed_hash("로봇")
    b = embed_hash("전혀 다른 이야기")
    # 유사도 낮아야
    cos = float(np.dot(a, b))
    assert cos < 0.95


def test_embed_falls_back_to_hash_when_ollama_fails(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.embed.embed_ollama", return_value=None
    )
    v = embed("hello", model="x")
    assert v.shape[0] == 256  # hash dim


def test_embed_empty_returns_zero_vector() -> None:
    v = embed("   ", model="x")
    assert float(np.linalg.norm(v)) == 0.0
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_embed.py -v
git add src/news_briefing/analysis/embed.py src/news_briefing/config.py .env.example tests/test_embed.py tests/test_config.py
git commit -m "feat(analysis): Ollama embedding client with hash-based fallback"
```

(test_config 수정 — 새 field 반영)

---

## Task 3: RAG 인덱싱 + 질의 엔진

**Files:**
- Create: `src/news_briefing/analysis/rag.py`
- Create: `tests/test_rag.py`

- [ ] **Step 1: rag.py**

```python
# src/news_briefing/analysis/rag.py
"""RAG 질의 엔진 — 브리핑 JSON 인덱싱 + 검색 + LLM 답변."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from news_briefing.analysis.embed import embed
from news_briefing.analysis.llm import _call_claude
from news_briefing.storage.embeddings import (
    EmbeddingRow,
    has_embedding,
    similarity_search,
    upsert_embedding,
)
from news_briefing.storage.queries import record_query

log = logging.getLogger(__name__)


ANSWER_PROMPT = (
    "당신은 금융·경제 브리핑 조수다. 아래 컨텍스트만 바탕으로 "
    "사용자 질문에 한국어로 답해줘.\n\n"
    "컨텍스트:\n{context}\n\n"
    "질문: {query}\n\n"
    "규칙:\n"
    "- 컨텍스트에 없는 내용은 추측하지 말고 '자료에 없어요' 라고 써\n"
    "- '매수 유망', '추천', '목표가' 같은 투자 유인 표현 금지\n"
    "- 답 끝에 참조한 doc_id 를 [출처: doc_id1, doc_id2] 형식으로 나열\n"
    "- 2~4 문장 이내 간결하게. 존댓말 '~요'"
)


@dataclass(frozen=True, slots=True)
class RagAnswer:
    query: str
    answer: str
    sources: list[dict]  # [{"doc_id":..., "score":..., "content":...}]


def _doc_id_for(source: str, ext_id: str) -> str:
    return f"{source}:{ext_id}"


def _format_signal_for_index(signal: dict, date: str) -> tuple[str, str, dict]:
    """briefing JSON 의 signal dict → (doc_id, indexable_text, metadata)."""
    doc_id = _doc_id_for(signal.get("source", "dart"), signal["id"])
    text = (
        f"[{date}] {signal.get('company', '')} — {signal.get('headline', '')}. "
        f"{signal.get('summary', '')}"
    )
    metadata = {
        "date": date,
        "company": signal.get("company", ""),
        "score": signal.get("score", 0),
        "url": signal.get("url", ""),
    }
    return doc_id, text, metadata


def _format_news_for_index(news: dict, date: str) -> tuple[str, str, dict]:
    doc_id = _doc_id_for(news.get("source", "rss"), news["id"])
    text = f"[{date}] {news.get('title', '')}. {news.get('summary', '')}"
    metadata = {
        "date": date,
        "source": news.get("source", ""),
        "category": news.get("category", ""),
        "url": news.get("url", ""),
    }
    return doc_id, text, metadata


def index_briefing(
    conn: sqlite3.Connection, briefing_path: Path, *, embed_model: str
) -> int:
    """Briefing JSON 의 시그널·뉴스를 임베딩 DB 에 일괄 추가.

    이미 인덱싱된 doc_id 는 스킵. 반환: 신규 인덱싱된 문서 수.
    """
    data = json.loads(briefing_path.read_text(encoding="utf-8"))
    date = data.get("date", "")
    count = 0

    to_index: list[tuple[str, str, str, dict]] = []  # (doc_id, source, text, metadata)

    # economy.signals + hero
    economy = data.get("tabs", {}).get("economy", {})
    for s in economy.get("signals", []):
        doc_id, text, meta = _format_signal_for_index(s, date)
        to_index.append((doc_id, s.get("source", "dart"), text, meta))
    hero = data.get("hero")
    if hero:
        doc_id, text, meta = _format_signal_for_index(hero, date)
        to_index.append((doc_id, hero.get("source", "dart"), text, meta))

    # economy.news + current.*
    for n in economy.get("news", []):
        doc_id, text, meta = _format_news_for_index(n, date)
        to_index.append((doc_id, n.get("source", "rss"), text, meta))
    current = data.get("tabs", {}).get("current", {})
    for cat in ("politics", "society", "international", "tech"):
        for n in current.get(cat, []):
            doc_id, text, meta = _format_news_for_index(n, date)
            to_index.append((doc_id, n.get("source", "rss"), text, meta))

    for doc_id, source, text, meta in to_index:
        if has_embedding(conn, doc_id):
            continue
        vec = embed(text, model=embed_model)
        upsert_embedding(
            conn,
            EmbeddingRow(
                doc_id=doc_id,
                source=source,
                content=text,
                vector=vec,
                metadata=meta,
            ),
        )
        count += 1
    return count


def answer_query(
    conn: sqlite3.Connection,
    query: str,
    *,
    embed_model: str,
    top_k: int = 5,
    record: bool = True,
) -> RagAnswer:
    q_vec = embed(query, model=embed_model)
    hits = similarity_search(conn, q_vec, top_k=top_k)
    if not hits:
        return RagAnswer(
            query=query,
            answer="자료가 아직 인덱싱되지 않았어요.",
            sources=[],
        )

    # 컨텍스트 조립 (상위 k 개)
    context_lines = [
        f"[{row.doc_id}] {row.content}" for row, _ in hits
    ]
    context = "\n".join(context_lines)

    try:
        answer = _call_claude(
            ANSWER_PROMPT.format(context=context, query=query), timeout=60
        ).strip()
    except Exception as e:
        log.error("RAG answer LLM 실패: %s", e)
        answer = "자료 검색은 됐지만 요약 생성에 실패했어요. 잠시 후 다시 시도해주세요."

    sources = [
        {
            "doc_id": row.doc_id,
            "score": round(score, 3),
            "content": row.content[:200],
            "metadata": row.metadata,
        }
        for row, score in hits
    ]
    result = RagAnswer(query=query, answer=answer, sources=sources)
    if record:
        record_query(
            conn,
            query=query,
            answer=answer,
            sources=sources,
            model="claude-cli+ollama-embed",
        )
    return result
```

- [ ] **Step 2: Test**

```python
# tests/test_rag.py
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from news_briefing.analysis.rag import answer_query, index_briefing
from news_briefing.storage.db import init_schema
from news_briefing.storage.embeddings import count_embeddings


def _write_briefing(path: Path) -> None:
    data = {
        "date": "2026-04-22",
        "generatedAt": "x",
        "version": 1,
        "hero": None,
        "tabs": {
            "current": {
                "politics": [
                    {
                        "id": "p1",
                        "source": "rss:yonhap-politics",
                        "title": "국회 원내대표 협상",
                        "summary": "여야 협상 진행",
                        "url": "https://yonhap.example/p1",
                        "curationScore": 70,
                    }
                ],
                "society": [],
                "international": [],
                "tech": [],
            },
            "economy": {
                "indices": [],
                "signals": [
                    {
                        "id": "s1",
                        "source": "dart",
                        "company": "삼성전자",
                        "headline": "자기주식취득결정",
                        "summary": "자사주 3,000억원 매수",
                        "score": 80,
                        "direction": "positive",
                        "url": "https://dart.example/s1",
                    }
                ],
                "news": [],
            },
            "picks": {"domestic": [], "foreign": []},
        },
        "glossary": {},
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_index_briefing_populates_embeddings(
    tmp_path: Path, memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    path = tmp_path / "2026-04-22.json"
    _write_briefing(path)

    mocker.patch(
        "news_briefing.analysis.rag.embed",
        side_effect=lambda text, model: np.array([1.0, 0.0], dtype=np.float32),
    )
    n = index_briefing(memory_db, path, embed_model="nomic-embed-text")
    # signal 1 + politics 1 = 2
    assert n == 2
    assert count_embeddings(memory_db) == 2


def test_index_is_idempotent_by_doc_id(
    tmp_path: Path, memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    path = tmp_path / "2026-04-22.json"
    _write_briefing(path)
    mocker.patch(
        "news_briefing.analysis.rag.embed",
        side_effect=lambda text, model: np.array([1.0, 0.0], dtype=np.float32),
    )
    n1 = index_briefing(memory_db, path, embed_model="m")
    n2 = index_briefing(memory_db, path, embed_model="m")
    assert n1 == 2
    assert n2 == 0  # 재실행 시 추가 없음


def test_answer_query_uses_top_hits_and_records(
    tmp_path: Path, memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    path = tmp_path / "2026-04-22.json"
    _write_briefing(path)

    # deterministic embedding — signal 은 [1,0], politics 는 [0,1]
    def fake_embed(text, model):
        if "자기주식" in text or "자사주" in text or "삼성" in text:
            return np.array([1.0, 0.0], dtype=np.float32)
        if "원내대표" in text or "협상" in text:
            return np.array([0.0, 1.0], dtype=np.float32)
        # 쿼리
        if "자사주" in text:
            return np.array([1.0, 0.0], dtype=np.float32)
        return np.array([0.5, 0.5], dtype=np.float32)

    mocker.patch("news_briefing.analysis.rag.embed", side_effect=fake_embed)
    mocker.patch(
        "news_briefing.analysis.rag._call_claude",
        return_value="삼성전자 자사주 매수 공시가 있어요. [출처: dart:s1]",
    )

    index_briefing(memory_db, path, embed_model="m")
    result = answer_query(memory_db, "삼성전자 자사주 매수 있었나?", embed_model="m")
    assert "삼성" in result.answer
    assert result.sources[0]["doc_id"] == "dart:s1"

    # 쿼리 기록
    from news_briefing.storage.queries import list_recent_queries
    recent = list_recent_queries(memory_db)
    assert len(recent) == 1


def test_answer_query_empty_index(
    memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    mocker.patch(
        "news_briefing.analysis.rag.embed",
        return_value=np.array([1.0, 0.0], dtype=np.float32),
    )
    mocker.patch("news_briefing.analysis.rag._call_claude")
    result = answer_query(memory_db, "아무거나", embed_model="m")
    assert "인덱싱" in result.answer
    assert result.sources == []


def test_answer_query_llm_failure_has_graceful_message(
    tmp_path: Path, memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    path = tmp_path / "2026-04-22.json"
    _write_briefing(path)
    mocker.patch(
        "news_briefing.analysis.rag.embed",
        side_effect=lambda text, model: np.array([1.0, 0.0], dtype=np.float32),
    )
    mocker.patch(
        "news_briefing.analysis.rag._call_claude",
        side_effect=RuntimeError("LLM down"),
    )
    index_briefing(memory_db, path, embed_model="m")
    result = answer_query(memory_db, "질문", embed_model="m")
    assert "요약 생성에 실패" in result.answer
    # sources 는 있어야 (검색은 성공)
    assert len(result.sources) > 0
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_rag.py -v
git add src/news_briefing/analysis/rag.py tests/test_rag.py
git commit -m "feat(analysis): RAG engine (index briefing JSON + similarity + LLM answer + history)"
```

---

## Task 4: CLI `ask` + orchestrator 자동 인덱싱

**Files:**
- Modify: `src/news_briefing/orchestrator.py` — morning 시 신규 briefing 자동 인덱싱
- Modify: `src/news_briefing/cli.py` — `ask <query>` 서브커맨드

- [ ] **Step 1: Orchestrator 자동 인덱싱**

```python
# orchestrator.py — write_briefing 직후 추가
from news_briefing.analysis.rag import index_briefing

# ...
briefing_json_path = write_briefing(
    public_briefings_dir=cfg.public_briefings_dir, briefing=briefing
)
# Week 4: RAG 자동 인덱싱 (Ollama 켜져있을 때만 효과적, 없어도 hash fallback)
try:
    indexed = index_briefing(
        conn, briefing_json_path, embed_model=cfg.ollama_embed_model
    )
    log.info("RAG 인덱싱: %d 신규 문서", indexed)
except Exception as e:
    log.warning("RAG 인덱싱 실패: %s", e)
```

- [ ] **Step 2: CLI `ask`**

```python
def _cmd_ask(args) -> int:
    from news_briefing.analysis.rag import answer_query
    from news_briefing.storage.db import connect

    cfg = load_config()
    conn = connect(cfg.db_path)
    try:
        result = answer_query(
            conn, args.query, embed_model=cfg.ollama_embed_model, top_k=args.top_k
        )
        print()
        print(result.answer)
        print()
        print(f"출처 {len(result.sources)}건:")
        for s in result.sources:
            print(f"  - {s['doc_id']} (유사도 {s['score']:.3f})")
            if s.get("metadata", {}).get("url"):
                print(f"    {s['metadata']['url']}")
    finally:
        conn.close()
    return 0

# subparser
p_ask = sub.add_parser("ask", help="RAG 자유 질의")
p_ask.add_argument("query", help="질의 내용")
p_ask.add_argument("--top-k", type=int, default=5)
p_ask.set_defaults(func=_cmd_ask)
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest 2>&1 | tail -5
git add src/news_briefing/orchestrator.py src/news_briefing/cli.py
git commit -m "feat: morning auto-indexes briefing for RAG + CLI 'ask' subcommand"
```

---

## Task 5: Weekly report LLM 에세이 업그레이드 + trending themes

**Files:**
- Modify: `src/news_briefing/delivery/weekly.py`
- Modify: `tests/test_weekly.py`
- Create: `tests/test_weekly_essay.py`

- [ ] **Step 1: Essay generator**

```python
# weekly.py 수정
from news_briefing.analysis.llm import _call_claude

ESSAY_PROMPT = (
    "당신은 금융·경제 브리핑 필자다. 아래 이번 주 상위 시그널·트렌드를 보고 "
    "500자 내외의 '이번 주 핵심 흐름' 에세이를 한국어로 써줘.\n\n"
    "상위 시그널:\n{signals}\n\n"
    "주목 테마: {themes}\n\n"
    "규칙:\n"
    "- 반말·느낌표 금지, 존댓말 '~요'\n"
    "- '매수 유망' 등 투자 유인 표현 금지\n"
    "- 흐름을 잡고 '섹터별·테마별' 관점에서 해석\n"
    "- 마지막 한 단락은 다음 주 관찰 포인트"
)


def generate_essay(report: WeeklyReport) -> str | None:
    if not report.top_signals:
        return None
    signals_text = "\n".join(
        f"- {s.get('company','—')}: {s.get('headline','')} (점수 {s.get('score',0)})"
        for s in report.top_signals[:10]
    )
    themes_text = ", ".join(report.trending_themes) if report.trending_themes else "(없음)"
    try:
        return _call_claude(
            ESSAY_PROMPT.format(signals=signals_text, themes=themes_text),
            timeout=60,
        ).strip()
    except Exception as e:
        log.warning("weekly essay LLM 실패: %s", e)
        return None


def render_weekly_html(report: WeeklyReport, essay: str | None = None) -> str:
    rows: list[str] = []
    for s in report.top_signals:
        company = html.escape(s.get("company") or "—")
        headline = html.escape(s.get("headline") or "")
        score = s.get("score", 0)
        url = html.escape(s.get("url") or "#")
        rows.append(
            f'  <li><strong>{company}</strong>: {headline} '
            f'(점수 {score}) <a href="{url}">원문</a></li>'
        )
    body = "\n".join(rows) if rows else "  <li>이번 주 기록된 시그널이 없어요.</li>"

    essay_section = ""
    if essay:
        essay_paragraphs = "".join(
            f"<p>{html.escape(p)}</p>"
            for p in essay.split("\n\n") if p.strip()
        )
        essay_section = f'<section><h2>이번 주 핵심 흐름</h2>{essay_paragraphs}</section>'

    themes_section = ""
    if report.trending_themes:
        themes_html = "".join(
            f"<li>{html.escape(t)}</li>" for t in report.trending_themes
        )
        themes_section = (
            f'<section><h2>주목 테마</h2><ul>{themes_html}</ul></section>'
        )

    return (
        "<!doctype html>\n"
        '<html lang="ko"><head><meta charset="utf-8">'
        f"<title>주간 리포트 · {html.escape(report.week_id)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:720px;"
        "margin:2rem auto;padding:0 1rem;line-height:1.6}</style>"
        "</head><body>"
        f"<h1>주간 리포트 · {html.escape(report.week_id)}</h1>"
        f"<p>{html.escape(report.start_date)} ~ {html.escape(report.end_date)}</p>"
        f"{essay_section}"
        f"{themes_section}"
        f"<h2>주요 시그널 상위 {len(report.top_signals)}건</h2>"
        f"<ol>\n{body}\n</ol>"
        "</body></html>\n"
    )
```

- [ ] **Step 2: Collect trending themes from past 7 days**

```python
def collect_weekly(
    briefings_dir: Path,
    *,
    now: datetime | None = None,
    theme_keywords: dict[str, list[str]] | None = None,
) -> WeeklyReport:
    # ... 기존 로직 ...

    # 트렌드 테마 감지 (주간 전체 기간)
    trending: list[str] = []
    if theme_keywords:
        from news_briefing.analysis.trends import detect_trending_themes
        events: list[tuple[str, datetime]] = []
        for i in range(7):
            day_dt = start + timedelta(days=i)
            day = day_dt.strftime("%Y-%m-%d")
            path = briefings_dir / f"{day}.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            economy = data.get("tabs", {}).get("economy", {})
            for s in economy.get("signals", []):
                events.append((s.get("headline", ""), day_dt))
            for n in economy.get("news", []):
                events.append((n.get("title", ""), day_dt))
        trending = detect_trending_themes(events, theme_keywords=theme_keywords, now=end)

    return WeeklyReport(
        week_id=_iso_week(end),
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        top_signals=unique[:20],
        trending_themes=trending,
    )
```

- [ ] **Step 3: CLI weekly 에 essay + theme_keywords 연결**

```python
def _cmd_weekly(args):
    from news_briefing.delivery.weekly import (
        collect_weekly, generate_essay, render_weekly_html, write_weekly
    )
    from news_briefing.storage.db import connect
    from news_briefing.storage.themes import list_themes

    cfg = load_config()
    conn = connect(cfg.db_path)
    try:
        # theme_keywords: theme name_ko 로 매칭
        themes = list_themes(conn)
        theme_keywords = {t.theme_id: [t.name_ko] for t in themes}
    finally:
        conn.close()

    report = collect_weekly(
        cfg.public_briefings_dir, theme_keywords=theme_keywords
    )
    essay = generate_essay(report) if args.llm else None
    html_content = render_weekly_html(report, essay=essay)
    reports_dir = cfg.data_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{report.week_id}.html"
    path.write_text(html_content, encoding="utf-8")

    print(f"주간 리포트 생성: {path}")
    print(f"  {report.week_id} · {len(report.top_signals)}개 시그널 · 트렌드 {report.trending_themes}")
    if essay:
        print(f"  에세이 {len(essay)}자")
    return 0

p_weekly = sub.add_parser("weekly", help="주간 리포트 생성")
p_weekly.add_argument("--llm", action="store_true", help="LLM 에세이 포함 (느림)")
p_weekly.set_defaults(func=_cmd_weekly)
```

- [ ] **Step 4: Test**

```python
# test_weekly_essay.py
def test_generate_essay_calls_llm_with_signals(mocker) -> None:
    from news_briefing.delivery.weekly import WeeklyReport, generate_essay
    mocker.patch(
        "news_briefing.delivery.weekly._call_claude",
        return_value="이번 주는 반도체가 핵심이에요.",
    )
    r = WeeklyReport(
        "2026-W17", "2026-04-19", "2026-04-25",
        top_signals=[{"company": "삼성", "headline": "자사주", "score": 85}],
        trending_themes=["ai_semi"],
    )
    essay = generate_essay(r)
    assert essay == "이번 주는 반도체가 핵심이에요."


def test_generate_essay_empty_report_returns_none() -> None:
    from news_briefing.delivery.weekly import WeeklyReport, generate_essay
    r = WeeklyReport("x", "a", "b", [], [])
    assert generate_essay(r) is None


def test_render_includes_essay_when_provided() -> None:
    from news_briefing.delivery.weekly import WeeklyReport, render_weekly_html
    r = WeeklyReport(
        "2026-W17", "a", "b",
        top_signals=[{"company":"X","headline":"Y","score":70,"url":"u"}],
        trending_themes=["robotics"],
    )
    html = render_weekly_html(r, essay="첫 문단\n\n두 번째 문단")
    assert "핵심 흐름" in html
    assert "첫 문단" in html
    assert "두 번째 문단" in html
    assert "robotics" in html  # trending theme
```

- [ ] **Step 5: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_weekly.py tests/test_weekly_essay.py -v
git add src/news_briefing/delivery/weekly.py src/news_briefing/cli.py tests/test_weekly_essay.py
git commit -m "feat(weekly): LLM essay section + trending themes detection"
```

---

## Task 6: 경제 탭 theme banner — 백엔드

**Files:**
- Modify: `src/news_briefing/orchestrator.py`
- Modify: `src/news_briefing/delivery/json_builder.py`
- Modify: `tests/test_json_builder.py`

이번 주 trending 테마를 morning 시 계산해서 `tabs.economy.themeBanner` 에 세팅.

- [ ] **Step 1: json_builder — themeBanner 지원**

```python
def build_briefing_json(
    *,
    # ... 기존 ...
    theme_banner: dict | None = None,  # {"trendingThemes": [...], "reportUrl": "..."}
) -> dict:
    # ... 기존 ...
    economy = {
        "indices": [],
        "signals": [...],
        "news": [...],
    }
    if theme_banner and theme_banner.get("trendingThemes"):
        economy["themeBanner"] = theme_banner

    return {
        # ...
        "tabs": {
            # ...
            "economy": economy,
            # ...
        },
    }
```

- [ ] **Step 2: orchestrator — trending 감지 후 banner 주입**

```python
# orchestrator.run_morning 안
from news_briefing.analysis.trends import detect_trending_themes
from news_briefing.storage.themes import list_themes

themes = list_themes(conn)
theme_keywords = {t.theme_id: [t.name_ko] for t in themes}
# 이벤트: 오늘 new_items + 지난 7일 분 JSON 에서 읽어야 정확. Week 4 간소화:
# 오늘 new_items 의 제목만 사용 (spike 감지는 Week 4 후반 개선)
events = [(it.title, now) for it in new_items if it.kind != "news" or
          (it.extra or {}).get("category") == "stock"]
trending = detect_trending_themes(
    events, theme_keywords=theme_keywords, now=now
) if theme_keywords else []

theme_banner: dict | None = None
if trending:
    # theme_id → name_ko 복원
    name_by_id = {t.theme_id: t.name_ko for t in themes}
    trending_names = [name_by_id.get(tid, tid) for tid in trending]
    week_id = now.strftime("%Y") + "-W" + f"{now.isocalendar()[1]:02d}"
    theme_banner = {
        "trendingThemes": trending_names,
        "reportUrl": f"/report/{week_id}",
    }

briefing = build_briefing_json(
    # ... 기존 ...
    theme_banner=theme_banner,
)
```

- [ ] **Step 3: Test**

```python
def test_theme_banner_included_when_provided() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 23),
        scored_signals=[],
        economy_news=[],
        theme_banner={
            "trendingThemes": ["로봇", "AI 반도체"],
            "reportUrl": "/report/2026-W17",
        },
    )
    banner = data["tabs"]["economy"].get("themeBanner")
    assert banner is not None
    assert "로봇" in banner["trendingThemes"]


def test_theme_banner_omitted_when_no_trending() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 23),
        scored_signals=[],
        economy_news=[],
        theme_banner={"trendingThemes": [], "reportUrl": ""},
    )
    assert "themeBanner" not in data["tabs"]["economy"]
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_json_builder.py tests/test_orchestrator.py -v
git add src/news_briefing/delivery/json_builder.py src/news_briefing/orchestrator.py tests/test_json_builder.py
git commit -m "feat: economy.themeBanner with trending themes (Week 4 F12)"
```

---

## Task 7: 경제 탭 theme banner — 프론트엔드

**Files:**
- Create: `frontend/src/components/ThemeBanner.tsx`
- Modify: `frontend/src/app/page.tsx` (economy 분기에 banner 추가)

- [ ] **Step 1: ThemeBanner**

```tsx
// frontend/src/components/ThemeBanner.tsx
'use client'

import type { ThemeBanner as ThemeBannerType } from '@/lib/types'

export function ThemeBanner({ banner }: { banner: ThemeBannerType }) {
  if (banner.trendingThemes.length === 0) return null
  return (
    <section
      className="mx-4 mb-2.5"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card)',
        padding: '20px 22px',
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: 'var(--text-tertiary)',
          letterSpacing: '-0.01em',
          marginBottom: 10,
        }}
      >
        이번 주 주목 테마
      </div>
      <div className="flex flex-wrap gap-2" style={{ marginBottom: 14 }}>
        {banner.trendingThemes.map((theme) => (
          <span
            key={theme}
            style={{
              padding: '6px 10px',
              fontSize: 13,
              fontWeight: 700,
              color: 'var(--text-primary)',
              background: 'var(--bg-inset)',
              borderRadius: 999,
            }}
          >
            {theme}
          </span>
        ))}
      </div>
      {banner.reportUrl && (
        <a
          href={banner.reportUrl}
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--text-primary)',
          }}
        >
          주간 리포트 보기 →
        </a>
      )}
    </section>
  )
}
```

- [ ] **Step 2: page.tsx economy 분기에 삽입**

```tsx
// economy 분기 렌더 안에 HeroCard 위에:
{briefing.tabs.economy.themeBanner && (
  <ThemeBanner banner={briefing.tabs.economy.themeBanner} />
)}
{briefing.hero && <HeroCard signal={briefing.hero} dict={dict} />}
```

`import { ThemeBanner } from '@/components/ThemeBanner'` 추가.

- [ ] **Step 3: Build check + commit**

```bash
cd frontend && npm run build
git add frontend/src/
git commit -m "feat(frontend): ThemeBanner in economy tab (Week 4)"
```

---

## Task 8: E2E + pytest + ruff + push

- [ ] **Step 1: Ollama 설치 여부 체크 (선택)**

```bash
which ollama && ollama list
# 없으면 hash fallback 으로 동작
```

- [ ] **Step 2: Seed + dry-run + ask**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m news_briefing themes seed
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m news_briefing morning --dry-run
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m news_briefing ask "오늘 자사주 매수 공시 있었나?"
```

- [ ] **Step 3: Weekly LLM**

```bash
# Ollama 있을 때 essay 포함
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m news_briefing weekly --llm
# 또는 LLM 없이 fallback
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m news_briefing weekly
```

- [ ] **Step 4: pytest + ruff**

```bash
.venv/Scripts/python.exe -m pytest 2>&1 | tail -5
.venv/Scripts/python.exe -m ruff check src tests
```

- [ ] **Step 5: Frontend rebuild**

`theme banner` 는 dev server hot reload 로 반영. 유저가 경제 탭 접속해 배너가 렌더되는지 확인.

- [ ] **Step 6: Final commit + push**

```bash
git push  # 자격 증명 확인 필요
```

---

## Week 4 Definition of Done

- [ ] `python -m news_briefing ask "질문"` 실행 시 **10초 이내 답변 + 출처 ≥2건** (Ollama 설치 시). Ollama 미설치면 hash fallback 으로라도 동작
- [ ] 주간 리포트 HTML 에 **LLM 에세이 섹션**이 있음 (`--llm` 플래그 시)
- [ ] **경제 탭 상단 "이번 주 주목 테마" 배너** 렌더 (trending 감지 시)
- [ ] 배너 우측 "주간 리포트 보기 →" 링크 동작
- [ ] 쿼리 히스토리 `rag_queries` 테이블에 기록됨
- [ ] pytest 전체 pass + ruff clean

### 의도적으로 하지 않는 것

- 일요일 23:00 자동 weekly 트리거 (launchd/Task Scheduler 수동 등록 가이드만)
- 카톡 주간 리포트 링크 자동 전송 (manual 실행 유지)
- 쿼리 피드백 (good/bad) UI — CLI 에선 히스토리만
- Chroma 전환 (SQLite+numpy 유지)
- SEC company_tickers.json 로 CIK-ticker 확장 (EDGAR 범위 이관)
- 인포스탁 자동 크롤러 (seed 유지)

---

## Self-Review

**Spec coverage (ROADMAP Week 4 작업 항목 6개):**
1. 벡터 DB 구축 → T1 (SQLite+numpy 대체) ✅
2. 문서 인덱싱 파이프라인 → T3 (`index_briefing`) ✅
3. RAG 질의 엔진 → T3-4 (`answer_query` + CLI `ask`) ✅
4. 테마 배너 UI → T6-7 ✅
5. 주간 리포트 LLM 에세이 → T5 ✅
6. 쿼리 히스토리 → T1 (`rag_queries` 테이블) + T3 자동 기록 ✅

**Placeholder 없음. Type 일관성 확인.**

**Risks:**
- Ollama 미설치 시 hash fallback 은 의미 없는 유사도 반환 — 실제 품질은 hash 로는 확보 안 됨. 운영 시 Ollama + nomic-embed-text 설치 필수
- 첫 morning 실행 시 수백 건 인덱싱 느릴 수 있음 — 점진적 처리 (이미 인덱싱된 건 skip)
- 전체 테이블 스캔 코사인 — 수만 건 쌓이면 느려짐. 그 때 Chroma/FAISS 도입
