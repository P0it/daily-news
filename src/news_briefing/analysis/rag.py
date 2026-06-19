"""RAG 질의 엔진 — 브리핑 JSON 인덱싱 + 검색 + LLM 답변 (Week 4).

개인 용도 시스템이라 방향성 있는 판단(매수·매도·목표가)을 허용한다 (DECISIONS #14).
정확성을 위해 컨텍스트에 없는 내용은 추측하지 않는다는 규칙만 프롬프트에 유지.
"""
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
    "- 개인 용도이므로 매수·매도 방향, 강도 등급, 목표가 등 방향성 있는 판단을 제시해도 됨\n"
    "- 답 끝에 참조한 doc_id 를 [출처: doc_id1, doc_id2] 형식으로 나열\n"
    "- 2~4 문장 이내 간결하게. 존댓말 '~요'"
)


@dataclass(frozen=True, slots=True)
class RagAnswer:
    query: str
    answer: str
    sources: list[dict]


def _doc_id_for(source: str, ext_id: str) -> str:
    return f"{source}:{ext_id}"


def _format_signal_for_index(signal: dict, date: str) -> tuple[str, str, dict]:
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


def _format_pick_for_index(
    pick: dict, issue: dict, scope: str, date: str
) -> tuple[str, str, dict]:
    """추천 종목 → 임베딩 문서. ask 가 picks 를 검색할 수 있게 한다."""
    ticker = pick.get("ticker", "")
    doc_id = _doc_id_for("pick", f"{date}:{ticker}")
    text = (
        f"[{date}] {pick.get('name', '')}({ticker}) — 테마 {issue.get('asset', '')}. "
        f"{pick.get('description', '')} {issue.get('reason', '')}"
    )
    metadata = {
        "date": date,
        "ticker": ticker,
        "scope": scope,
        "theme": issue.get("asset", ""),
        "url": issue.get("url") or "",
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

    to_index: list[tuple[str, str, str, dict]] = []

    economy = data.get("tabs", {}).get("economy", {})
    hot_issues = economy.get("hotIssues", {})
    for scope in ("domestic", "foreign"):
        for issue in hot_issues.get(scope, []):
            for pick in issue.get("picks") or []:
                if not pick.get("ticker"):
                    continue
                doc_id, text, meta = _format_pick_for_index(pick, issue, scope, date)
                to_index.append((doc_id, "pick", text, meta))

    count = 0
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

    context_lines = [f"[{row.doc_id}] {row.content}" for row, _ in hits]
    context = "\n".join(context_lines)

    try:
        answer = _call_claude(
            ANSWER_PROMPT.format(context=context, query=query), timeout=60
        ).strip()
    except Exception as e:
        log.error("RAG answer LLM 실패: %s", e)
        answer = (
            "자료 검색은 됐지만 요약 생성에 실패했어요. "
            "잠시 후 다시 시도해주세요."
        )

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
