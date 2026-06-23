from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem
from news_briefing.delivery.json_builder import build_briefing_json, write_briefing


def _research_item(ext_id: str = "r1") -> CollectedItem:
    return CollectedItem(
        source="research",
        ext_id=ext_id,
        kind="disclosure",
        title="목표주가 상향",
        url="https://example.com",
        published_at=datetime(2026, 6, 15, 6, 0),
        company="삼성전자",
        company_code="005930",
        extra={"firm": "미래에셋", "tpDirection": "상향", "targetPricePct": 12.0},
    )


def _issue(asset: str, ticker: str) -> dict:
    return {
        "rank": 1,
        "asset": asset,
        "assetType": "theme",
        "direction": "positive",
        "signal": "수주 급증",
        "reason": "근거",
        "picks": [{"ticker": ticker, "name": ticker, "description": "수혜"}],
        "source": "SEC EDGAR",
        "url": None,
    }


def test_build_briefing_has_required_top_level_keys() -> None:
    data = build_briefing_json(date=datetime(2026, 6, 15, 6, 0))
    assert data["date"] == "2026-06-15"
    assert "generatedAt" in data
    assert data["version"] == 2
    # picks-only 스키마: economy 탭만, 뉴스·시사·AI·hero 없음
    assert set(data["tabs"].keys()) == {"economy"}
    assert "current" not in data["tabs"]
    assert "ai" not in data["tabs"]
    assert "hero" not in data
    econ = data["tabs"]["economy"]
    assert set(econ.keys()) == {"indices", "research", "etf", "hotIssues", "watchlist"}
    assert "signals" not in econ
    assert "news" not in econ


def test_hot_issues_passed_through() -> None:
    data = build_briefing_json(
        date=datetime(2026, 6, 15),
        hot_issues_foreign=[_issue("AI 인프라", "NVDA")],
        hot_issues_domestic=[_issue("방산", "012450")],
    )
    hot = data["tabs"]["economy"]["hotIssues"]
    assert hot["foreign"][0]["picks"][0]["ticker"] == "NVDA"
    assert hot["domestic"][0]["picks"][0]["ticker"] == "012450"


def test_hot_issues_empty_default() -> None:
    data = build_briefing_json(date=datetime(2026, 6, 15))
    hot = data["tabs"]["economy"]["hotIssues"]
    assert hot == {"domestic": [], "foreign": []}


def test_research_list_built() -> None:
    data = build_briefing_json(
        date=datetime(2026, 6, 15),
        research_scored=[(_research_item(), 82, "positive")],
    )
    research = data["tabs"]["economy"]["research"]
    assert len(research) == 1
    assert research[0]["company"] == "삼성전자"
    assert research[0]["tpDirection"] == "상향"
    assert research[0]["score"] == 82


def test_write_briefing_creates_json_and_index(tmp_path: Path) -> None:
    data = build_briefing_json(date=datetime(2026, 6, 15))
    written = write_briefing(public_briefings_dir=tmp_path, briefing=data)
    assert written.exists()
    assert written.name == "2026-06-15.json"

    index_path = tmp_path / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert "2026-06-15" in index["dates"]


def test_write_briefing_appends_new_date_to_index(tmp_path: Path) -> None:
    d1 = build_briefing_json(date=datetime(2026, 6, 14))
    d2 = build_briefing_json(date=datetime(2026, 6, 15))
    write_briefing(public_briefings_dir=tmp_path, briefing=d1)
    write_briefing(public_briefings_dir=tmp_path, briefing=d2)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["dates"] == ["2026-06-15", "2026-06-14"]
