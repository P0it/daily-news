"""Briefing JSON 생성 + frontend/public/briefings 에 기록.

ARCHITECTURE.md 6.4 스키마 준수.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from news_briefing.analysis.attention_phase import AttentionPhase, PHASE_EXCLUDE_THRESHOLD
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


def _source_group(source: str) -> str:
    """소스 → 언론사 그룹 (동일 언론사 중복 방지용)."""
    for keyword in ("bbc", "yonhap", "gnews", "hankyung", "mk", "ft", "anthropic", "openai", "hn"):
        if keyword in source:
            return keyword
    return source


def _diverse_cap(items: list[dict], cap: int) -> list[dict]:
    """소스 다양성 우선 + cap 적용.

    1순위: 소스 그룹별 1개씩 선택 (같은 언론사 2개 연속 방지).
    2순위: 여분 슬롯은 curation 순서로 채움.
    """
    seen: set[str] = set()
    result: list[dict] = []
    remainder: list[dict] = []
    for item in items:
        grp = _source_group(item.get("source", ""))
        if grp not in seen:
            seen.add(grp)
            result.append(item)
        else:
            remainder.append(item)
    return (result + remainder)[:cap]


def select_displayed_current(
    current_news: list[tuple[CollectedItem, int]] | None,
) -> list[CollectedItem]:
    """시사 탭에 실제 노출될 항목만 미리 선별해 반환.

    build_briefing_json 의 current 처리와 **동일한 기준**(카테고리별
    CURRENT_SECTION_CAPS + curation 내림차순 + 소스 다양성)을 적용한다.
    번역처럼 비용 큰 후처리를 '노출될 소수'에만 적용하기 위한 사전 선별 용도로,
    결과 집합이 최종 노출분과 일치한다. (전량 번역 → 선별 후 번역 최적화)
    """
    grouped: dict[str, list[tuple[CollectedItem, int]]] = {cat: [] for cat in CURRENT_SECTION_CAPS}
    for item, curation in current_news or []:
        cat = (item.extra or {}).get("category", "")
        if cat in grouped:
            grouped[cat].append((item, curation))

    displayed: list[CollectedItem] = []
    for cat, arr in grouped.items():
        arr.sort(key=lambda x: x[1], reverse=True)
        cap = CURRENT_SECTION_CAPS.get(cat, 5)
        seen_groups: set[str] = set()
        primary: list[CollectedItem] = []
        remainder: list[CollectedItem] = []
        for item, _curation in arr:
            grp = _source_group(item.source)
            if grp not in seen_groups:
                seen_groups.add(grp)
                primary.append(item)
            else:
                remainder.append(item)
        displayed.extend((primary + remainder)[:cap])
    return displayed


def _signal_to_dict(
    item: CollectedItem,
    score: int,
    direction: str,
    term_ids_by_id: dict[str, str] | None = None,
    thesis_check: dict | None = None,
    phase: AttentionPhase | None = None,
) -> dict:
    summary = item.body or ""
    d: dict = {
        "id": item.ext_id,
        "source": item.source.split(":")[0],  # 'dart', 'edgar', 'research' 등
        "company": item.company or "",
        "companyCode": item.company_code or None,
        "headline": item.title,
        "summary": summary,
        "score": score,
        "direction": direction,
        "scope": (
            "foreign"
            if item.source.startswith("edgar") or (item.extra or {}).get("scope") == "foreign"
            else "domestic"
        ),
        "time": item.published_at.isoformat(),
        "url": item.url,
        "glossaryTermId": (term_ids_by_id or {}).get(item.ext_id),
    }
    if phase is not None:
        d["attentionPhase"] = phase.phase
        d["attentionLabel"] = phase.label
        d["priceLead"] = round(phase.price_lead, 4)
    if thesis_check:
        d["thesisCheck"] = thesis_check
    return d


def _news_to_dict(
    item: CollectedItem,
    *,
    curation: int = 0,
    term_ids_by_id: dict[str, str] | None = None,
    summaries: dict[str, str] | None = None,
    title_translations: dict[str, str] | None = None,
) -> dict:
    scope, category = SOURCE_META.get(item.source, ("foreign", "stock"))
    extra_cat = (item.extra or {}).get("category", "")
    if extra_cat:
        category = extra_cat  # 파싱 시 덮어쓴 값 우선
    # LLM 생성 요약 우선 (F36), 없으면 원본 RSS description
    llm_summary = (summaries or {}).get(item.ext_id, "")
    summary_text = llm_summary if llm_summary else item.body
    # 해외 AI 뉴스 제목 번역 (Week 5b). 번역본이 있으면 title 자체를 교체
    title_ko = (title_translations or {}).get(item.ext_id, "")
    display_title = title_ko if title_ko else item.title
    publisher = (item.extra or {}).get("publisher", "")
    return {
        "id": item.ext_id,
        "source": item.source,
        "publisher": publisher,
        "title": display_title,
        "titleOriginal": item.title if title_ko else None,
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
    hot_issues_foreign: list[dict] | None = None,
    hot_issues_domestic: list[dict] | None = None,
    news_summaries: dict[str, str] | None = None,
    ai_title_translations: dict[str, str] | None = None,
    macro_indices: list | None = None,
    research_scored: list[tuple[CollectedItem, int, str]] | None = None,
    etf_snapshots: list | None = None,
    phase_map: dict[str, AttentionPhase] | None = None,
) -> dict:
    pm = phase_map or {}

    def _phase_sort_key(t: tuple) -> tuple:
        """Phase 1 → Phase 2 → Phase 3 → Phase 4 순, 같은 위상 내 점수 내림차순."""
        item, score, _ = t
        ph = pm[item.ext_id].phase if item.ext_id in pm else 2
        return (ph, -score)

    filtered_for_economy = [s for s in scored_signals if s[1] >= ECONOMY_SIGNAL_THRESHOLD]
    # 위상 기반 정렬: Phase 1~2 우선, Phase 4 하단
    filtered_for_economy.sort(key=_phase_sort_key)

    hero = None
    # 히어로는 점수 기준 유지 (가장 중요한 단일 시그널)
    score_sorted = sorted(filtered_for_economy, key=lambda t: t[1], reverse=True)
    if score_sorted and score_sorted[0][1] >= HERO_THRESHOLD:
        it, score, direction = score_sorted[0]
        ph = pm.get(it.ext_id)
        hero = _signal_to_dict(it, score, direction, term_ids_by_id, phase=ph)
        filtered_for_economy = [s for s in filtered_for_economy if s[0].ext_id != it.ext_id]

    # 시사 탭 — 카테고리별 그루핑 + curation 정렬 + 소스 다양성 + cap
    current_grouped: dict[str, list[dict]] = {
        "politics": [],
        "society": [],
        "international": [],
        "tech": [],
    }
    for item, curation in current_news or []:
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
        current_grouped[cat] = _diverse_cap(arr, cap)

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
    economy_tab: dict = {
        "indices": indices_list,
        "signals": [
            _signal_to_dict(it, s, d, term_ids_by_id, phase=pm.get(it.ext_id))
            for it, s, d in filtered_for_economy
        ],
        "news": [
            _news_to_dict(n, term_ids_by_id=term_ids_by_id, summaries=news_summaries)
            for n in economy_news
        ],
    }
    # 증권사 리서치 리포트 (목표주가 상향/하향/신규)
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
    economy_tab["research"] = research_list

    # KRX ETF 순자산 상위 (자금 흐름 참고)
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
    economy_tab["etf"] = etf_list

    if hot_issues_foreign or hot_issues_domestic:
        economy_tab["hotIssues"] = {
            "domestic": hot_issues_domestic or [],
            "foreign": hot_issues_foreign or [],
        }

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
            item,
            term_ids_by_id=term_ids_by_id,
            summaries=news_summaries,
            title_translations=ai_title_translations,
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
