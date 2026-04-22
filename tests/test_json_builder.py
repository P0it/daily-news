from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem
from news_briefing.delivery.json_builder import build_briefing_json, write_briefing


def _item(title: str = "공시", ext_id: str = "x") -> CollectedItem:
    return CollectedItem(
        source="dart",
        ext_id=ext_id,
        kind="disclosure",
        title=title,
        url="https://example.com",
        published_at=datetime(2026, 4, 22, 6, 0),
        company="삼성전자",
        company_code="005930",
    )


def test_build_briefing_has_required_top_level_keys() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 22, 6, 0),
        scored_signals=[],
        economy_news=[],
    )
    assert data["date"] == "2026-04-22"
    assert "generatedAt" in data
    assert data["version"] == 1
    assert data["hero"] is None
    assert "current" in data["tabs"]
    assert "economy" in data["tabs"]
    assert data["glossary"] == {}


def test_hero_set_when_score_above_90() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 22),
        scored_signals=[(_item("횡령"), 95, "negative")],
        economy_news=[],
    )
    assert data["hero"] is not None
    assert data["hero"]["score"] == 95
    # hero 로 승격되면 economy.signals 에서 제외돼야
    assert len(data["tabs"]["economy"]["signals"]) == 0


def test_economy_signals_filtered_by_threshold() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 22),
        scored_signals=[
            (_item("t1", "1"), 80, "positive"),
            (_item("t2", "2"), 55, "neutral"),
            (_item("t3", "3"), 45, "neutral"),
        ],
        economy_news=[],
    )
    scores = [s["score"] for s in data["tabs"]["economy"]["signals"]]
    assert scores == [80]


def test_economy_signals_sorted_desc() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 22),
        scored_signals=[
            (_item("low", "a"), 65, "neutral"),
            (_item("high", "b"), 85, "mixed"),
            (_item("mid", "c"), 75, "positive"),
        ],
        economy_news=[],
    )
    scores = [s["score"] for s in data["tabs"]["economy"]["signals"]]
    assert scores == [85, 75, 65]


def test_glossary_map_included() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 22),
        scored_signals=[(_item("자기주식취득결정", "id1"), 80, "positive")],
        economy_news=[],
        glossary={
            "self_stock_buy": {
                "shortLabel": "자사주 매수",
                "explanation": "...",
                "direction": "positive",
            }
        },
        term_ids_by_id={"id1": "self_stock_buy"},
    )
    assert "self_stock_buy" in data["glossary"]
    assert data["tabs"]["economy"]["signals"][0]["glossaryTermId"] == "self_stock_buy"


def test_write_briefing_creates_json_and_index(tmp_path: Path) -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 22), scored_signals=[], economy_news=[]
    )
    written = write_briefing(public_briefings_dir=tmp_path, briefing=data)
    assert written.exists()
    assert written.name == "2026-04-22.json"

    index_path = tmp_path / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert "2026-04-22" in index["dates"]


def test_write_briefing_appends_new_date_to_index(tmp_path: Path) -> None:
    d1 = build_briefing_json(date=datetime(2026, 4, 21), scored_signals=[], economy_news=[])
    d2 = build_briefing_json(date=datetime(2026, 4, 22), scored_signals=[], economy_news=[])
    write_briefing(public_briefings_dir=tmp_path, briefing=d1)
    write_briefing(public_briefings_dir=tmp_path, briefing=d2)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    # 최신순 정렬
    assert index["dates"] == ["2026-04-22", "2026-04-21"]
