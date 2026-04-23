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
from news_briefing.collectors.rss import SOURCE_META

SCHEMA_VERSION = 1
HERO_THRESHOLD = 90
ECONOMY_SIGNAL_THRESHOLD = 60


def _epoch(iso: str) -> float:
    """ISO 시간 문자열 → epoch. 파싱 실패 시 0."""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0

# PRD F31 — 시사 탭 섹션별 노출 cap
CURRENT_SECTION_CAPS = {
    "politics": 5,
    "society": 3,
    "international": 3,
    "tech": 2,
}

# Week 5b AI 탭 cap (국내/해외 각각)
AI_SECTION_CAP = 20


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


def _news_to_dict(
    item: CollectedItem,
    *,
    curation: int = 0,
    term_ids_by_id: dict[str, str] | None = None,
    summaries: dict[str, str] | None = None,
) -> dict:
    scope, category = SOURCE_META.get(item.source, ("foreign", "stock"))
    extra_cat = (item.extra or {}).get("category", "")
    if extra_cat:
        category = extra_cat  # 파싱 시 덮어쓴 값 우선
    # LLM 생성 요약 우선 (F36), 없으면 원본 RSS description
    llm_summary = (summaries or {}).get(item.ext_id, "")
    summary_text = llm_summary if llm_summary else item.body
    publisher = (item.extra or {}).get("publisher", "")
    return {
        "id": item.ext_id,
        "source": item.source,
        "publisher": publisher,
        "title": item.title,
        "summary": summary_text,
        "url": item.url,
        "thumbnail": None,
        "time": item.published_at.isoformat(),
        "scope": scope,
        "category": category,
        "glossaryTermId": (term_ids_by_id or {}).get(item.ext_id),
        "curationScore": curation,
    }


def build_briefing_json(
    *,
    date: datetime,
    scored_signals: list[tuple[CollectedItem, int, str]],
    economy_news: list[CollectedItem],
    current_news: list[tuple[CollectedItem, int]] | None = None,
    ai_news: list[CollectedItem] | None = None,
    glossary: dict[str, dict] | None = None,
    term_ids_by_id: dict[str, str] | None = None,
    picks: PicksResult | None = None,
    theme_banner: dict | None = None,
    news_summaries: dict[str, str] | None = None,
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

    # 시사 탭 — 카테고리별 그루핑 + curation 정렬 + cap
    current_grouped: dict[str, list[dict]] = {
        "politics": [],
        "society": [],
        "international": [],
        "tech": [],
    }
    for item, curation in (current_news or []):
        cat = (item.extra or {}).get("category", "")
        if cat in current_grouped:
            current_grouped[cat].append(
                _news_to_dict(
                    item,
                    curation=curation,
                    term_ids_by_id=term_ids_by_id,
                    summaries=news_summaries,
                )
            )
    for cat, arr in current_grouped.items():
        arr.sort(key=lambda x: x.get("curationScore", 0), reverse=True)
        cap = CURRENT_SECTION_CAPS.get(cat, 5)
        current_grouped[cat] = arr[:cap]

    # Week 5a (DECISIONS #13): picks 를 economy 내부로 이동
    economy_tab: dict = {
        "indices": [],
        "picks": picks_tab,
        "signals": [
            _signal_to_dict(it, s, d, term_ids_by_id)
            for it, s, d in filtered_for_economy
        ],
        "news": [
            _news_to_dict(
                n, term_ids_by_id=term_ids_by_id, summaries=news_summaries
            )
            for n in economy_news
        ],
    }
    if theme_banner and theme_banner.get("trendingThemes"):
        economy_tab["themeBanner"] = theme_banner

    # Week 5b: AI 탭 — 소스 품질 가중 + 최신성 정렬
    # 공식 블로그·GeekNews·YouTube·HN 먼저, Google News 는 뒤 (노이즈 최소화)
    def _ai_source_priority(src: str) -> int:
        if src.startswith("rss:yt-"):
            return 0  # YouTube — 영상 소스, 품질 상위
        if src == "rss:anthropic" or src == "rss:openai":
            return 1  # 공식 모델 업데이트 — 최고 신뢰도
        if src == "rss:geeknews":
            return 2  # 개발자 커뮤니티 큐레이션
        if src.startswith("rss:hn-"):
            return 3  # Hacker News
        return 9  # Google News aggregator (마지막)

    ai_domestic: list[dict] = []
    ai_foreign: list[dict] = []
    for item in ai_news or []:
        scope, _ = SOURCE_META.get(item.source, ("foreign", "ai"))
        entry = _news_to_dict(
            item, term_ids_by_id=term_ids_by_id, summaries=news_summaries
        )
        entry["_priority"] = _ai_source_priority(item.source)  # 정렬 후 제거
        if scope == "domestic":
            ai_domestic.append(entry)
        else:
            ai_foreign.append(entry)
    # (품질 우선, 최신순) 으로 정렬
    ai_domestic.sort(key=lambda x: (x["_priority"], -_epoch(x.get("time", ""))))
    ai_foreign.sort(key=lambda x: (x["_priority"], -_epoch(x.get("time", ""))))
    ai_domestic = ai_domestic[:AI_SECTION_CAP]
    ai_foreign = ai_foreign[:AI_SECTION_CAP]
    for entry in ai_domestic + ai_foreign:
        entry.pop("_priority", None)

    result: dict = {
        "date": date.strftime("%Y-%m-%d"),
        "generatedAt": datetime.now(UTC).isoformat(),
        "version": SCHEMA_VERSION,
        "hero": hero,
        "tabs": {
            "current": current_grouped,
            "economy": economy_tab,
            "ai": {"domestic": ai_domestic, "foreign": ai_foreign},
        },
        "glossary": glossary or {},
    }
    return result


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
