from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from news_briefing.analysis.rag import answer_query, index_briefing
from news_briefing.storage.db import init_schema
from news_briefing.storage.embeddings import count_embeddings
from news_briefing.storage.queries import list_recent_queries


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
    assert n2 == 0


def test_answer_query_uses_top_hits_and_records(
    tmp_path: Path, memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    path = tmp_path / "2026-04-22.json"
    _write_briefing(path)

    def fake_embed(text, model):
        # 자사주/삼성 관련 텍스트는 [1,0], 원내대표 관련은 [0,1]
        if "자사주" in text or "자기주식" in text or "삼성" in text:
            return np.array([1.0, 0.0], dtype=np.float32)
        if "원내대표" in text or "협상" in text:
            return np.array([0.0, 1.0], dtype=np.float32)
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
    assert len(result.sources) > 0
