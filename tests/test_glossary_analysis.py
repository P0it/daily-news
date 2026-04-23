from __future__ import annotations

import sqlite3

from news_briefing.analysis.glossary import (
    TERM_CATALOG,
    detect_term,
    ensure_glossary_entry,
)
from news_briefing.storage.db import init_schema
from news_briefing.storage.glossary import get_glossary_entry


def test_detect_term_for_self_stock() -> None:
    assert detect_term("자기주식취득결정") == "self_stock_buy"


def test_detect_term_for_insider() -> None:
    assert detect_term("임원ㆍ주요주주특정증권등소유상황보고서") == "insider_trade"


def test_detect_term_returns_none_for_unknown() -> None:
    assert detect_term("알수없는 공시") is None


def test_term_catalog_has_minimum_entries() -> None:
    # SIGNALS.md 3.2 기준 최소 7개
    assert len(TERM_CATALOG) >= 7


def test_current_affairs_terms_detected() -> None:
    assert detect_term("더불어민주당 원내대표 협상") == "floor_leader"
    assert detect_term("대법원 전원합의체 선고") == "plenary_assembly"
    assert detect_term("30조 규모 추경 편성") == "supplementary_budget"
    assert detect_term("올해 국정감사 정쟁") == "national_audit"


def test_term_catalog_has_current_affairs_minimum() -> None:
    current_terms = [
        "plenary_assembly",
        "floor_leader",
        "supplementary_budget",
        "national_audit",
    ]
    for t in current_terms:
        assert t in TERM_CATALOG


def test_macro_economic_terms_detected() -> None:
    assert detect_term("한은 기준금리 0.25%p 인하 결정") == "base_rate"
    assert detect_term("미국 소비자물가 3.2% 상승") == "cpi"
    assert detect_term("GDP 성장률 1.8% 전망") == "gdp"
    assert detect_term("FOMC 이후 달러 약세") == "fed_fomc"
    assert detect_term("환율 1,400원 돌파") == "exchange_rate"
    assert detect_term("경기침체 우려에 증시 하락") == "recession"


def test_term_catalog_has_macro_minimum() -> None:
    macro_terms = ["base_rate", "cpi", "gdp", "fed_fomc", "exchange_rate", "recession"]
    for t in macro_terms:
        assert t in TERM_CATALOG


def test_ensure_glossary_uses_seed_when_defined(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    entry = ensure_glossary_entry(memory_db, "self_stock_buy", lang="ko")
    assert entry is not None
    assert "자사주" in entry.short_label or "자기주식" in entry.short_label
    cached = get_glossary_entry(memory_db, "self_stock_buy", "ko")
    assert cached == entry


def test_ensure_glossary_falls_back_to_llm_for_unseeded_term(
    memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    TERM_CATALOG["_test_term"] = ("테스트용어", "_test_term_keyword")

    mock_llm = mocker.patch(
        "news_briefing.analysis.glossary._generate_explanation_via_llm",
        return_value=("테스트용어", "LLM 생성 해설", "neutral"),
    )
    try:
        entry = ensure_glossary_entry(memory_db, "_test_term", lang="ko")
        assert mock_llm.call_count == 1
        assert entry is not None
        assert entry.explanation == "LLM 생성 해설"
    finally:
        del TERM_CATALOG["_test_term"]


def test_ensure_glossary_returns_cached_without_llm(
    memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    mock_llm = mocker.patch(
        "news_briefing.analysis.glossary._generate_explanation_via_llm"
    )
    ensure_glossary_entry(memory_db, "self_stock_buy", lang="ko")
    ensure_glossary_entry(memory_db, "self_stock_buy", lang="ko")
    assert mock_llm.call_count == 0


def test_ensure_glossary_unknown_term_returns_none(
    memory_db: sqlite3.Connection,
) -> None:
    init_schema(memory_db)
    assert ensure_glossary_entry(memory_db, "nonexistent_term_id", lang="ko") is None
