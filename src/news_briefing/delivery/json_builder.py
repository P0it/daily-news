"""Briefing JSON 생성 + frontend/public/briefings 에 기록.

ARCHITECTURE.md 6.4 스키마 준수.
Week 2a: hero, tabs.current, tabs.economy, glossary 포함.
Week 2b: tabs.picks 추가 예정.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from news_briefing.analysis.picks import PicksResult
from news_briefing.collectors.base import CollectedItem

SCHEMA_VERSION = 1
HERO_THRESHOLD = 90
ECONOMY_SIGNAL_THRESHOLD = 60


def _signal_to_dict(
    item: CollectedItem,
    score: int,
    direction: str,
    term_ids_by_id: dict[str, str] | None = None,
) -> dict:
    return {
        "id": item.ext_id,
        "source": item.source.split(":")[0],  # 'dart' or 'edgar'
        "company": item.company or "",
        "companyCode": item.company_code or None,
        "headline": item.title,
        "summary": item.body or "",
        "score": score,
        "direction": direction,
        "scope": "foreign" if item.source.startswith("edgar") else "domestic",
        "time": item.published_at.isoformat(),
        "url": item.url,
        "glossaryTermId": (term_ids_by_id or {}).get(item.ext_id),
    }


def _news_to_dict(item: CollectedItem) -> dict:
    return {
        "id": item.ext_id,
        "source": item.source,
        "title": item.title,
        "summary": item.body,
        "url": item.url,
        "thumbnail": None,
        "time": item.published_at.isoformat(),
        "scope": "domestic" if item.source in ("rss:hankyung", "rss:mk") else "foreign",
        "glossaryTermId": None,
        "curationScore": 0,
    }


def build_briefing_json(
    *,
    date: datetime,
    scored_signals: list[tuple[CollectedItem, int, str]],
    economy_news: list[CollectedItem],
    glossary: dict[str, dict] | None = None,
    term_ids_by_id: dict[str, str] | None = None,
    picks: PicksResult | None = None,
) -> dict:
    filtered_for_economy = [
        s for s in scored_signals if s[1] >= ECONOMY_SIGNAL_THRESHOLD
    ]
    filtered_for_economy.sort(key=lambda t: t[1], reverse=True)

    hero = None
    if filtered_for_economy and filtered_for_economy[0][1] >= HERO_THRESHOLD:
        it, score, direction = filtered_for_economy[0]
        hero = _signal_to_dict(it, score, direction, term_ids_by_id)
        filtered_for_economy = filtered_for_economy[1:]

    picks_tab: dict[str, list[dict]] = {"domestic": [], "foreign": []}
    if picks:
        picks_tab["domestic"] = [
            _signal_to_dict(it, s, d, term_ids_by_id) for it, s, d in picks.domestic
        ]
        picks_tab["foreign"] = [
            _signal_to_dict(it, s, d, term_ids_by_id) for it, s, d in picks.foreign
        ]

    return {
        "date": date.strftime("%Y-%m-%d"),
        "generatedAt": datetime.now(UTC).isoformat(),
        "version": SCHEMA_VERSION,
        "hero": hero,
        "tabs": {
            "current": {
                "politics": [],
                "society": [],
                "international": [],
                "tech": [],
            },
            "economy": {
                "indices": [],
                "signals": [
                    _signal_to_dict(it, s, d, term_ids_by_id)
                    for it, s, d in filtered_for_economy
                ],
                "news": [_news_to_dict(n) for n in economy_news],
            },
            "picks": picks_tab,
        },
        "glossary": glossary or {},
    }


def write_briefing(*, public_briefings_dir: Path, briefing: dict) -> Path:
    public_briefings_dir.mkdir(parents=True, exist_ok=True)
    date = briefing["date"]
    path = public_briefings_dir / f"{date}.json"
    path.write_text(
        json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # index.json 업데이트
    index_path = public_briefings_dir / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"dates": []}
    if date not in index["dates"]:
        index["dates"].append(date)
        index["dates"].sort(reverse=True)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return path
