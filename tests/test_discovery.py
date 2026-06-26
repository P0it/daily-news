"""발굴 LLM 리서치 파서·병합 단위 테스트 (LLM 호출 없음)."""

from __future__ import annotations

from news_briefing.analysis.discovery import (
    _apply_thesis,
    _parse_research,
    _scan_objects,
)


def test_parse_clean_array() -> None:
    raw = '[{"ticker": "AAA", "thesis": "t"}]'
    assert list(_parse_research(raw).keys()) == ["AAA"]


def test_parse_fenced() -> None:
    raw = '```json\n[{"ticker": "BBB", "thesis": "t"}]\n```'
    assert list(_parse_research(raw).keys()) == ["BBB"]


def test_parse_prose_then_objects_without_brackets() -> None:
    # LLM 이 배열 괄호를 빠뜨리고 객체만 나열한 복구 케이스
    raw = '다음과 같습니다:\n{"ticker": "AAA", "thesis": "t1"},\n{"ticker": "BBB", "thesis": "t2"}'
    assert sorted(_parse_research(raw).keys()) == ["AAA", "BBB"]


def test_parse_single_object() -> None:
    assert list(_parse_research('{"ticker": "DDD", "thesis": "t"}').keys()) == ["DDD"]


def test_parse_garbage_returns_empty() -> None:
    assert _parse_research("죄송하지만 도와드릴 수 없습니다") == {}


def test_scan_objects_handles_nested_braces() -> None:
    raw = '{"ticker": "EEE", "related_etf": {"ticker": "069500", "name": "x"}}'
    objs = _scan_objects(raw)
    assert len(objs) == 1
    assert objs[0]["ticker"] == "EEE"


def test_apply_thesis_merges_fields_and_etf() -> None:
    item = {
        "ticker": "AAA",
        "thesis": None,
        "whyUndiscovered": None,
        "keyRisks": None,
        "confirmCatalysts": None,
        "valuationNote": None,
        "relatedEtf": None,
    }
    thesis = {
        "thesis": "저평가 우량 성장이에요",
        "why_undiscovered": "시장이 메모리 사이클로만 봐서요",
        "key_risks": "사이클 둔화",
        "confirm_catalysts": "HBM 수주",
        "valuation_note": "동종 대비 디스카운트",
        "related_etf": {"ticker": "069500", "name": "KODEX 200", "confidence": "low"},
    }
    _apply_thesis(item, thesis)
    assert item["thesis"] == "저평가 우량 성장이에요"
    assert item["whyUndiscovered"] == "시장이 메모리 사이클로만 봐서요"
    assert item["relatedEtf"] == {"ticker": "069500", "name": "KODEX 200", "confidence": "low"}


def test_apply_thesis_ignores_incomplete_etf() -> None:
    item = {
        "ticker": "AAA",
        "relatedEtf": None,
        "thesis": None,
        "whyUndiscovered": None,
        "keyRisks": None,
        "confirmCatalysts": None,
        "valuationNote": None,
    }
    _apply_thesis(item, {"thesis": "t", "related_etf": {"ticker": "069500"}})  # name 누락
    assert item["relatedEtf"] is None
