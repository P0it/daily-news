from __future__ import annotations

from news_briefing.analysis.spillover import _parse_spillover


def test_parse_basic() -> None:
    raw = """{"items":[
        {"idx":0,"beneficiaries":[
            {"name":"경쟁제약","ticker":"001234","reason":"생산 차질 반사이익",
             "confidence":"medium"}]},
        {"idx":1,"beneficiaries":[]}
    ]}"""
    out = _parse_spillover(raw, n_items=2)
    assert set(out) == {0}  # 빈 배열 항목은 결과에 없음
    assert out[0][0]["name"] == "경쟁제약"
    assert out[0][0]["code"] == "001234"
    assert out[0][0]["confidence"] == "medium"


def test_parse_strips_codeblock_and_prose() -> None:
    raw = '```json\n{"items":[{"idx":0,"beneficiaries":[{"name":"B","ticker":"NVDA"}]}]}\n```'
    out = _parse_spillover(raw, n_items=1)
    assert out[0][0]["name"] == "B"
    assert out[0][0]["confidence"] == "low"  # 누락 시 low 기본


def test_parse_out_of_range_idx_dropped() -> None:
    raw = '{"items":[{"idx":5,"beneficiaries":[{"name":"X","ticker":"1"}]}]}'
    assert _parse_spillover(raw, n_items=2) == {}


def test_parse_invalid_confidence_coerced_low() -> None:
    raw = '{"items":[{"idx":0,"beneficiaries":[{"name":"X","ticker":"1","confidence":"high"}]}]}'
    out = _parse_spillover(raw, n_items=1)
    assert out[0][0]["confidence"] == "low"


def test_parse_garbage_returns_empty() -> None:
    assert _parse_spillover("not json at all", n_items=3) == {}


def test_parse_empty_name_skipped() -> None:
    raw = (
        '{"items":[{"idx":0,"beneficiaries":['
        '{"name":"","ticker":"1"},{"name":"OK","ticker":"2"}]}]}'
    )
    out = _parse_spillover(raw, n_items=1)
    assert [b["name"] for b in out[0]] == ["OK"]
