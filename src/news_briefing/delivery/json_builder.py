"""Briefing JSON 생성 + frontend/public/briefings 에 기록.

종목추천 전용 스키마(v2): 뉴스·시그널·시사·AI 표시를 제거하고
economy 탭에 picks(hotIssues)와 보조 맥락(지수·리서치·ETF)만 남긴다.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem

SCHEMA_VERSION = 2


def build_briefing_json(
    *,
    date: datetime,
    hot_issues_foreign: list[dict] | None = None,
    hot_issues_domestic: list[dict] | None = None,
    macro_indices: list | None = None,
    research_scored: list[tuple[CollectedItem, int, str]] | None = None,
    etf_snapshots: list | None = None,
) -> dict:
    """picks 중심 브리핑 JSON 생성.

    economy 탭 = 시장지수 + 증권사 리서치 + KRX ETF + hotIssues(picks).
    """
    indices_list = [
        {
            "symbol": m.symbol,
            "ticker": m.ticker,
            "close": m.close,
            "change": m.change,
            "changePct": m.change_pct,
            "currency": m.currency,
            "group": m.group,
        }
        for m in (macro_indices or [])
    ]

    research_list = [
        {
            "id": it.ext_id,
            "company": it.company or "",
            "companyCode": it.company_code or None,
            "firm": (it.extra or {}).get("firm", ""),
            "reportTitle": (it.extra or {}).get("reportTitle", it.title),
            "targetPrice": (it.extra or {}).get("targetPrice", 0),
            "targetPriceChange": (it.extra or {}).get("targetPriceChange", 0),
            "targetPricePct": (it.extra or {}).get("targetPricePct", 0.0),
            "tpDirection": (it.extra or {}).get("tpDirection", "유지"),
            "direction": d,
            "score": s,
            "url": it.url,
            "time": it.published_at.isoformat(),
        }
        for it, s, d in (research_scored or [])
    ]

    etf_list = [
        {
            "code": e.code,
            "name": e.name,
            "theme": e.theme,
            "close": e.close,
            "change": e.change,
            "changePct": e.change_pct,
        }
        for e in (etf_snapshots or [])
    ]

    economy_tab: dict = {
        "indices": indices_list,
        "research": research_list,
        "etf": etf_list,
        "hotIssues": {
            "domestic": hot_issues_domestic or [],
            "foreign": hot_issues_foreign or [],
        },
    }

    return {
        "date": date.strftime("%Y-%m-%d"),
        "generatedAt": datetime.now(UTC).isoformat(),
        "version": SCHEMA_VERSION,
        "tabs": {"economy": economy_tab},
    }


def write_briefing(*, public_briefings_dir: Path, briefing: dict) -> Path:
    public_briefings_dir.mkdir(parents=True, exist_ok=True)
    date = briefing["date"]
    path = public_briefings_dir / f"{date}.json"
    path.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")

    # index.json 업데이트
    index_path = public_briefings_dir / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"dates": []}
    if date not in index["dates"]:
        index["dates"].append(date)
        index["dates"].sort(reverse=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    return path
