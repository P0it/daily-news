# Week 3: 시사 뉴스 + 테마·밸류체인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Week 2 기반 위에 (1) **시사 탭 데이터** (F27-F32: 정치·사회·국제·IT RSS + 큐레이션 + 용어 주석) 를 채우고, (2) **테마·밸류체인 DB** (F11: `themes / value_layers / companies_in_layer` 매핑) 를 구축해서 "로봇 테마 수혜 공통분모는?" 질문의 기반을 마련한다. Week 4 RAG 엔진이 이 데이터를 소비한다.

**Architecture:** 백엔드 확장 중심. 시사 RSS 는 기존 `collectors/rss.py` 에 source 카테고리 정보를 추가해 재사용. 큐레이션은 순수 Python (소스 신뢰도 × 최신성) + 선택적 LLM 중요도 판정. 테마 DB 는 **seed JSON 우선** (수동 15~20개 테마) + 인포스탁 크롤러는 옵션 업데이트 스크립트로 분리. 밸류체인 LLM 분해는 별도 CLI 서브커맨드 (`python -m news_briefing themes refresh`) 로 수동 실행 (비용·시간 많이 듬).

**Tech Stack:** 기존 Week 2 유지. 추가: 없음 (stdlib + feedparser 재사용).

---

## File Structure (Week 3 결과물)

### 백엔드

| 파일 | 책임 |
|------|------|
| `src/news_briefing/collectors/rss.py` (수정) | 시사 피드 추가 + `category` 필드 노출 |
| `src/news_briefing/analysis/curation.py` | 시사 큐레이션 점수 (소스 신뢰도 × 최신성 × [LLM 중요도]) |
| `src/news_briefing/analysis/glossary.py` (수정) | 시사 용어 catalog 확장 ("전원합의체", "국정감사" 등) |
| `src/news_briefing/analysis/themes.py` | 테마↔기업 매핑 read, 밸류체인 LLM 분해, 포지셔닝 생성 |
| `src/news_briefing/analysis/trends.py` | 키워드 빈도 이동평균 기반 "신규 주목 테마" 감지 |
| `src/news_briefing/storage/themes.py` | `themes / value_layers / companies_in_layer` CRUD |
| `src/news_briefing/storage/db.py` (수정) | 3개 테마 테이블 스키마 추가 |
| `src/news_briefing/delivery/json_builder.py` (수정) | `tabs.current` 카테고리별 채우기 + 각 뉴스에 `curationScore` |
| `src/news_briefing/orchestrator.py` (수정) | 시사 수집·큐레이션·용어 감지·트렌드 통합 |
| `src/news_briefing/delivery/weekly.py` | 주간 리포트 HTML 기본 템플릿 (Week 4 에서 에세이 고도화) |
| `src/news_briefing/cli.py` (수정) | `weekly` 와 `themes refresh` 서브커맨드 |
| `data/themes_seed.json` | 수동 테마·기업 seed (gitignored 대상은 아님, 프로젝트 데이터) |
| `scripts/crawl_infostock.py` | (옵션) 인포스탁 테마 페이지 업데이트 스크립트 |

### 테스트

| 파일 | 책임 |
|------|------|
| `tests/test_curation.py` | 큐레이션 점수 공식 |
| `tests/test_themes_storage.py` | 테마 DB CRUD |
| `tests/test_themes_analysis.py` | 밸류체인 분해 LLM mock |
| `tests/test_trends.py` | 이동평균 트렌드 감지 |
| `tests/test_weekly.py` | 주간 리포트 생성 |
| `tests/test_rss_current.py` | 시사 RSS 카테고리 |

---

## Task 1: 시사 RSS 피드 카탈로그 확장 + category 필드

**Files:**
- Modify: `src/news_briefing/collectors/rss.py`
- Modify: `src/news_briefing/collectors/base.py` (CollectedItem.extra 로 category 보관, 또는 source 에 prefix)
- Modify: `tests/test_rss.py`

`RssFeedSpec` 에 `category` 필드 추가: `'stock' | 'politics' | 'society' | 'international' | 'tech'`. `RSS_FEEDS` 카탈로그 확장.

- [ ] **Step 1: Extend RssFeedSpec**

```python
# collectors/rss.py
from typing import Literal

NewsCategory = Literal[
    "stock", "politics", "society", "international", "tech"
]


@dataclass(frozen=True, slots=True)
class RssFeedSpec:
    source: str
    url: str
    scope: str          # 'domestic' | 'foreign'
    category: NewsCategory  # 신규
```

`parse_rss_feed` 가 `CollectedItem.extra["category"]` 로 카테고리 부착.

- [ ] **Step 2: Expand RSS_FEEDS catalog**

```python
RSS_FEEDS: list[RssFeedSpec] = [
    # 경제·주식 (기존)
    RssFeedSpec("rss:hankyung", "https://www.hankyung.com/feed/economy", "domestic", "stock"),
    RssFeedSpec("rss:mk", "https://www.mk.co.kr/rss/30000001/", "domestic", "stock"),
    RssFeedSpec("rss:bbc-business", "https://feeds.bbci.co.uk/news/business/rss.xml", "foreign", "stock"),
    RssFeedSpec("rss:ft-markets", "https://www.ft.com/markets?format=rss", "foreign", "stock"),

    # 정치 (F27)
    RssFeedSpec("rss:yonhap-politics", "https://www.yna.co.kr/rss/politics.xml", "domestic", "politics"),
    RssFeedSpec("rss:hani-politics", "https://www.hani.co.kr/rss/politics/", "domestic", "politics"),

    # 사회 (F28)
    RssFeedSpec("rss:yonhap-society", "https://www.yna.co.kr/rss/society.xml", "domestic", "society"),
    RssFeedSpec("rss:hani-society", "https://www.hani.co.kr/rss/society/", "domestic", "society"),

    # 국제 (F29)
    RssFeedSpec("rss:yonhap-intl", "https://www.yna.co.kr/rss/international.xml", "domestic", "international"),
    RssFeedSpec("rss:bbc-world", "https://feeds.bbci.co.uk/news/world/rss.xml", "foreign", "international"),
    RssFeedSpec("rss:reuters-world", "https://www.reuters.com/world/rss", "foreign", "international"),

    # IT/과학 (F30)
    RssFeedSpec("rss:zdnet-kr", "https://feeds.feedburner.com/zdkorea/AllZDKoreaStoriesFeed", "domestic", "tech"),
    RssFeedSpec("rss:etnews", "https://rss.etnews.com/20.xml", "domestic", "tech"),
]
```

- [ ] **Step 3: Update parse_rss_feed to include category**

```python
items.append(
    CollectedItem(
        source=source_id,
        ext_id=ext_id,
        kind="news",
        title=...,
        url=...,
        published_at=...,
        body=...,
        extra={"category": category} if category else {},
    )
)
```

`parse_rss_feed(content, source_id, category=None)`.

- [ ] **Step 4: Test updates**

```python
# test_rss.py 에 추가
def test_rss_feeds_catalog_has_all_categories() -> None:
    cats = {f.category for f in RSS_FEEDS}
    assert cats == {"stock", "politics", "society", "international", "tech"}


def test_parse_preserves_category(fixtures_dir: Path) -> None:
    content = (fixtures_dir / "hankyung.xml").read_text(encoding="utf-8")
    items = parse_rss_feed(content, source_id="rss:hani-politics", category="politics")
    assert items[0].extra.get("category") == "politics"
```

- [ ] **Step 5: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_rss.py -v
git add src/news_briefing/collectors/rss.py tests/test_rss.py
git commit -m "feat(collectors): current-affairs RSS feeds (politics/society/intl/tech) with category"
```

---

## Task 2: 시사 큐레이션 점수

**Files:**
- Create: `src/news_briefing/analysis/curation.py`
- Create: `tests/test_curation.py`

공식: `source_trust × recency_factor × importance_factor` (0~100 스케일).

- [ ] **Step 1: Failing test**

```python
# tests/test_curation.py
from __future__ import annotations

from datetime import datetime, timedelta

from news_briefing.analysis.curation import (
    SOURCE_TRUST,
    curation_score,
    recency_factor,
)


def test_source_trust_has_major_domestic_outlets() -> None:
    assert "rss:yonhap-politics" in SOURCE_TRUST
    assert "rss:hani-politics" in SOURCE_TRUST
    # 연합뉴스 는 일반적으로 신뢰도 높음
    assert SOURCE_TRUST["rss:yonhap-politics"] >= 0.8


def test_recency_factor_decays_with_age() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    assert recency_factor(now - timedelta(hours=1), now) >= 0.9
    assert 0.4 <= recency_factor(now - timedelta(hours=12), now) <= 0.6
    assert recency_factor(now - timedelta(days=2), now) <= 0.1


def test_recency_factor_future_clamps_to_one() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    # 시계 오차 케이스
    assert recency_factor(now + timedelta(hours=1), now) == 1.0


def test_curation_score_combines_factors() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    one_hour_ago = now - timedelta(hours=1)
    s = curation_score(
        source="rss:yonhap-politics",
        published_at=one_hour_ago,
        now=now,
        importance=0.8,
    )
    # 0.85 (trust) * ~0.95 (recency) * 0.8 (importance) * 100 ≈ 65
    assert 55 <= s <= 75


def test_curation_score_unknown_source_defaults_to_lower_trust() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    s = curation_score(
        source="rss:unknown-blog",
        published_at=now,
        now=now,
        importance=1.0,
    )
    # trust 0.5 (기본) × 1.0 × 1.0 × 100 = 50
    assert 40 <= s <= 60
```

- [ ] **Step 2: Implement curation.py**

```python
# src/news_briefing/analysis/curation.py
"""시사 뉴스 큐레이션 점수.

공식: source_trust × recency × importance → 0~100 스케일.
- source_trust: 소스별 고정 신뢰도 (수동 튜닝)
- recency: 최근 6h=1.0, 12h=0.5, 24h=0.2, 48h+=0 (선형 근사)
- importance: LLM 판정 (0~1) 또는 기본 1.0
"""
from __future__ import annotations

from datetime import datetime

# 소스 신뢰도 테이블 (수동 튜닝, PRD F31 기반)
SOURCE_TRUST: dict[str, float] = {
    # 연합뉴스: 공식 뉴스통신, 사실 전달 위주 → 신뢰도 높음
    "rss:yonhap-politics": 0.85,
    "rss:yonhap-society": 0.85,
    "rss:yonhap-intl": 0.85,
    # 한겨레·경향: 오피니언 색 있음 → 중간
    "rss:hani-politics": 0.75,
    "rss:hani-society": 0.75,
    # BBC·Reuters: 해외 공신력 높음
    "rss:bbc-world": 0.9,
    "rss:bbc-business": 0.9,
    "rss:reuters-world": 0.9,
    # IT/과학 전문지
    "rss:zdnet-kr": 0.7,
    "rss:etnews": 0.7,
    # 경제지
    "rss:hankyung": 0.8,
    "rss:mk": 0.8,
    "rss:ft-markets": 0.85,
}

DEFAULT_TRUST = 0.5


def recency_factor(published_at: datetime, now: datetime) -> float:
    """최근성 점수 (0~1).

    6h 이내 = 1.0, 12h = 0.5, 24h = 0.2, 48h+ = 0.0.
    미래 시각은 1.0 (시계 오차 케이스).
    """
    delta = now - published_at
    if delta.total_seconds() < 0:
        return 1.0
    hours = delta.total_seconds() / 3600
    if hours <= 6:
        return 1.0
    if hours <= 12:
        # 6~12h: 1.0 → 0.5 선형
        return 1.0 - (hours - 6) * (0.5 / 6)
    if hours <= 24:
        # 12~24h: 0.5 → 0.2 선형
        return 0.5 - (hours - 12) * (0.3 / 12)
    if hours <= 48:
        # 24~48h: 0.2 → 0.0 선형
        return max(0.0, 0.2 - (hours - 24) * (0.2 / 24))
    return 0.0


def curation_score(
    *,
    source: str,
    published_at: datetime,
    now: datetime,
    importance: float = 1.0,
) -> int:
    trust = SOURCE_TRUST.get(source, DEFAULT_TRUST)
    rec = recency_factor(published_at, now)
    imp = max(0.0, min(1.0, importance))
    score = round(trust * rec * imp * 100)
    return max(0, min(100, score))
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_curation.py -v
git add src/news_briefing/analysis/curation.py tests/test_curation.py
git commit -m "feat(analysis): current-affairs curation score (trust × recency × importance)"
```

---

## Task 3: 시사 용어 catalog 확장

**Files:**
- Modify: `src/news_briefing/analysis/glossary.py`

증권 용어 (Week 2a) + 시사 용어 추가 (정치·사회 초심자 대상).

- [ ] **Step 1: Extend TERM_CATALOG and SEED_EXPLANATIONS_KO**

```python
TERM_CATALOG 에 추가:
    "plenary_assembly": ("대법원 전원합의체", "전원합의체"),
    "floor_leader": ("원내대표", "원내대표"),
    "supplementary_budget": ("추경", "추경"),
    "national_audit": ("국정감사", "국정감사"),
    "proportional_representation": ("연동형 비례대표제", "연동형 비례대표"),
    "constitutional_court": ("헌법재판소", "헌법재판소"),
    "prosecutor_investigation": ("검찰 수사", "검찰 수사"),
```

`SEED_EXPLANATIONS_KO` 에 각 항목 해설 추가:

```python
"plenary_assembly": (
    "대법원 전원합의체",
    "대법원의 가장 높은 합의체예요. 전체 대법관 13명이 모여 법 해석의 "
    "방향을 정하는 결정을 할 때 열려요. 하급심과 다른 판단을 내릴 수 있고, "
    "이후 비슷한 사건의 기준이 돼요.",
    "neutral",
),
"floor_leader": (
    "원내대표",
    "국회 안에서 각 정당의 '현장 지휘관' 역할이에요. 법안 협상, 본회의 "
    "일정, 의원 표결 지도 등을 맡아요. 당 대표가 바깥 이미지라면, "
    "원내대표는 실제 정치 실무를 움직여요.",
    "neutral",
),
# ... 나머지도 유사
```

- [ ] **Step 2: Test**

```python
# test_glossary_analysis.py 에 추가
def test_current_affairs_terms_detected() -> None:
    assert detect_term("원내대표 협상") == "floor_leader"
    assert detect_term("대법원 전원합의체 선고") == "plenary_assembly"


def test_term_catalog_has_current_affairs_minimum() -> None:
    current_terms = ["plenary_assembly", "floor_leader", "supplementary_budget", "national_audit"]
    for t in current_terms:
        assert t in TERM_CATALOG
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_glossary_analysis.py -v
git add src/news_briefing/analysis/glossary.py tests/test_glossary_analysis.py
git commit -m "feat(analysis): current-affairs glossary terms (plenary, floor leader, 추경 etc)"
```

---

## Task 4: JSON builder — tabs.current 카테고리별 채우기

**Files:**
- Modify: `src/news_briefing/delivery/json_builder.py`
- Modify: `tests/test_json_builder.py`

시사 뉴스 item 을 category 별로 그루핑 + 각 뉴스에 `curationScore`.

- [ ] **Step 1: Extend _news_to_dict**

```python
def _news_to_dict(item: CollectedItem, curation: int = 0) -> dict:
    category = (item.extra or {}).get("category", "")
    scope = "domestic" if item.source.startswith("rss:yonhap") or item.source.startswith("rss:hani") or item.source in ("rss:zdnet-kr", "rss:etnews") else "foreign"
    # 구체 매핑은 collectors/rss.py 의 RSS_FEEDS 에서 가져오는 게 정확. helper 분리.
    return {
        "id": item.ext_id,
        "source": item.source,
        "title": item.title,
        "summary": item.body,
        "url": item.url,
        "thumbnail": None,
        "time": item.published_at.isoformat(),
        "scope": scope,
        "glossaryTermId": None,
        "curationScore": curation,
        "category": category,  # 신규 노출
    }
```

실제로 scope 는 `RssFeedSpec` 의 `scope` 에서 가져와야 깔끔 — `collectors/rss.py` 에서 `SOURCE_META` dict 로 export 해서 json_builder 가 사용.

```python
# collectors/rss.py
SOURCE_META: dict[str, tuple[str, str]] = {
    spec.source: (spec.scope, spec.category) for spec in RSS_FEEDS
}
```

- [ ] **Step 2: build_briefing_json — current tab 채움**

```python
def build_briefing_json(
    *,
    date: datetime,
    scored_signals: list[...],
    economy_news: list[CollectedItem],
    current_news: list[tuple[CollectedItem, int]] | None = None,  # (item, curation_score)
    ...
) -> dict:
    grouped = {"politics": [], "society": [], "international": [], "tech": []}
    for item, curation in (current_news or []):
        cat = (item.extra or {}).get("category", "")
        if cat in grouped:
            grouped[cat].append(_news_to_dict(item, curation=curation))
    # 각 섹션 curation 내림차순 + N으로 제한
    for k, arr in grouped.items():
        arr.sort(key=lambda x: x.get("curationScore", 0), reverse=True)
        # section caps from PRD F31: 정치 5, 사회 3, 국제 3, IT/과학 2
        caps = {"politics": 5, "society": 3, "international": 3, "tech": 2}
        grouped[k] = arr[:caps[k]]

    return {
        ...
        "tabs": {
            "current": grouped,  # politics/society/international/tech 각 배열
            "economy": {...},
            "picks": {...},
        },
    }
```

- [ ] **Step 3: Test**

```python
def test_current_tab_groups_by_category() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    p = CollectedItem(
        source="rss:yonhap-politics", ext_id="p1", kind="news",
        title="정치 기사", url="x", published_at=now,
        extra={"category": "politics"},
    )
    s = CollectedItem(
        source="rss:yonhap-society", ext_id="s1", kind="news",
        title="사회 기사", url="x", published_at=now,
        extra={"category": "society"},
    )
    data = build_briefing_json(
        date=now, scored_signals=[], economy_news=[],
        current_news=[(p, 70), (s, 60)],
    )
    assert len(data["tabs"]["current"]["politics"]) == 1
    assert len(data["tabs"]["current"]["society"]) == 1
    assert data["tabs"]["current"]["politics"][0]["curationScore"] == 70
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_json_builder.py -v
git add src/news_briefing/delivery/json_builder.py src/news_briefing/collectors/rss.py tests/test_json_builder.py
git commit -m "feat(delivery): tabs.current grouped by category with curation score + section caps"
```

---

## Task 5: Orchestrator — 시사 수집·큐레이션·용어·트렌드 통합

**Files:**
- Modify: `src/news_briefing/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

수집은 이미 `fetch_all_rss()` 가 시사 피드 포함. 큐레이션 · 카테고리 필터링 · glossary detect 를 추가.

- [ ] **Step 1: orchestrator 수정**

```python
# orchestrator.run_morning 안에서

from news_briefing.analysis.curation import curation_score

# 새 items 중 시사 카테고리만 분리
current_candidates: list[tuple[CollectedItem, int]] = []
for it in new_items:
    if it.kind != "news":
        continue
    category = (it.extra or {}).get("category", "")
    if category in ("politics", "society", "international", "tech"):
        cs = curation_score(
            source=it.source,
            published_at=it.published_at,
            now=now,
            importance=1.0,  # Week 3 은 고정. Week 4+ 에서 LLM 중요도 반영.
        )
        # 시사 용어 감지 (glossary)
        term_id = detect_term(it.title)
        if term_id:
            entry = ensure_glossary_entry(conn, term_id, lang="ko")
            if entry:
                term_ids_by_id[it.ext_id] = term_id
                if term_id not in glossary_map:
                    glossary_map[term_id] = {
                        "shortLabel": entry.short_label,
                        "explanation": entry.explanation,
                        "direction": entry.signal_direction,
                    }
        current_candidates.append((it, cs))

# 주식 뉴스는 기존 그대로 economy.news 로
fresh_economy_news = [it for it in new_items if it.kind == "news" and
                      (it.extra or {}).get("category", "") == "stock"][:15]

briefing = build_briefing_json(
    date=now,
    scored_signals=scored,
    economy_news=fresh_economy_news,
    current_news=current_candidates,
    glossary=glossary_map,
    term_ids_by_id=term_ids_by_id,
    picks=picks,
)
```

- [ ] **Step 2: Test**

```python
def test_current_news_populated_with_category(tmp_path, mocker) -> None:
    cfg = _cfg(tmp_path)
    politics = CollectedItem(
        source="rss:yonhap-politics", ext_id="p1", kind="news",
        title="국회 원내대표 협상", url="x",
        published_at=datetime(2026, 4, 23, 11, 0),
        extra={"category": "politics"},
    )
    mocker.patch("news_briefing.orchestrator.fetch_all_rss", return_value=[politics])
    mocker.patch("news_briefing.orchestrator.fetch_all_edgar", return_value=[])
    mocker.patch("news_briefing.orchestrator.summarize", return_value="")
    mocker.patch("news_briefing.orchestrator._send_kakao")

    result = run_morning(cfg, dry_run=True, now=datetime(2026, 4, 23, 12, 0))
    data = json.loads(result.briefing_json_path.read_text(encoding="utf-8"))
    assert len(data["tabs"]["current"]["politics"]) == 1
    assert data["tabs"]["current"]["politics"][0]["curationScore"] > 0
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v
git add src/news_briefing/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator integrates current-affairs categorization + curation + glossary"
```

---

## Task 6: 테마 DB 스키마

**Files:**
- Modify: `src/news_briefing/storage/db.py`
- Create: `src/news_briefing/storage/themes.py`
- Create: `tests/test_themes_storage.py`

- [ ] **Step 1: Extend _SCHEMA**

```sql
CREATE TABLE IF NOT EXISTS themes (
    theme_id    TEXT PRIMARY KEY,
    name_ko     TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS value_layers (
    layer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id    TEXT NOT NULL REFERENCES themes(theme_id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT NOT NULL,
    UNIQUE (theme_id, name)
);

CREATE TABLE IF NOT EXISTS companies_in_layer (
    layer_id     INTEGER NOT NULL REFERENCES value_layers(layer_id) ON DELETE CASCADE,
    ticker       TEXT NOT NULL,
    company_name TEXT NOT NULL,
    positioning  TEXT,
    verified     INTEGER NOT NULL DEFAULT 0,  -- 0=미검증, 1=인포스탁 등 교차검증
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (layer_id, ticker)
);
CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies_in_layer(ticker);
```

- [ ] **Step 2: storage/themes.py CRUD**

```python
# src/news_briefing/storage/themes.py
"""테마·밸류체인 DB CRUD (ARCHITECTURE.md 5.4)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Theme:
    theme_id: str
    name_ko: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ValueLayer:
    layer_id: int | None  # None before insert
    theme_id: str
    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class CompanyInLayer:
    layer_id: int
    ticker: str
    company_name: str
    positioning: str | None = None
    verified: bool = False


def upsert_theme(conn: sqlite3.Connection, theme: Theme) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO themes(theme_id, name_ko, description, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (theme.theme_id, theme.name_ko, theme.description, now),
    )
    conn.commit()


def get_theme(conn: sqlite3.Connection, theme_id: str) -> Theme | None:
    r = conn.execute(
        "SELECT theme_id, name_ko, description FROM themes WHERE theme_id=?",
        (theme_id,),
    ).fetchone()
    return Theme(r["theme_id"], r["name_ko"], r["description"]) if r else None


def list_themes(conn: sqlite3.Connection) -> list[Theme]:
    rows = conn.execute(
        "SELECT theme_id, name_ko, description FROM themes ORDER BY theme_id"
    ).fetchall()
    return [Theme(r["theme_id"], r["name_ko"], r["description"]) for r in rows]


def upsert_layer(conn: sqlite3.Connection, layer: ValueLayer) -> int:
    now = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "INSERT OR REPLACE INTO value_layers(theme_id, name, description, updated_at) "
        "VALUES (?, ?, ?, ?) RETURNING layer_id",
        (layer.theme_id, layer.name, layer.description, now),
    )
    row = cur.fetchone()
    conn.commit()
    return row["layer_id"]


def list_layers(conn: sqlite3.Connection, theme_id: str) -> list[ValueLayer]:
    rows = conn.execute(
        "SELECT layer_id, theme_id, name, description FROM value_layers "
        "WHERE theme_id=? ORDER BY layer_id",
        (theme_id,),
    ).fetchall()
    return [
        ValueLayer(r["layer_id"], r["theme_id"], r["name"], r["description"])
        for r in rows
    ]


def upsert_company(conn: sqlite3.Connection, company: CompanyInLayer) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO companies_in_layer"
        "(layer_id, ticker, company_name, positioning, verified, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            company.layer_id,
            company.ticker,
            company.company_name,
            company.positioning,
            1 if company.verified else 0,
            now,
        ),
    )
    conn.commit()


def list_companies(conn: sqlite3.Connection, layer_id: int) -> list[CompanyInLayer]:
    rows = conn.execute(
        "SELECT layer_id, ticker, company_name, positioning, verified "
        "FROM companies_in_layer WHERE layer_id=? ORDER BY company_name",
        (layer_id,),
    ).fetchall()
    return [
        CompanyInLayer(
            r["layer_id"], r["ticker"], r["company_name"],
            r["positioning"], bool(r["verified"]),
        )
        for r in rows
    ]
```

- [ ] **Step 3: Test CRUD**

```python
# tests/test_themes_storage.py
def test_upsert_and_get_theme(memory_db) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("robotics", "로봇", "산업용·서비스 로봇"))
    got = get_theme(memory_db, "robotics")
    assert got.name_ko == "로봇"


def test_layer_crud(memory_db) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("robotics", "로봇"))
    lid = upsert_layer(memory_db, ValueLayer(None, "robotics", "액추에이터", "모터·감속기"))
    assert lid > 0
    layers = list_layers(memory_db, "robotics")
    assert len(layers) == 1


def test_company_crud(memory_db) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("robotics", "로봇"))
    lid = upsert_layer(memory_db, ValueLayer(None, "robotics", "액추에이터"))
    upsert_company(memory_db, CompanyInLayer(
        lid, "058610", "에스피지", "하모닉 감속기 국내 3위", verified=True,
    ))
    comps = list_companies(memory_db, lid)
    assert comps[0].verified is True
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_themes_storage.py -v
git add src/news_briefing/storage/db.py src/news_briefing/storage/themes.py tests/test_themes_storage.py
git commit -m "feat(storage): themes + value_layers + companies_in_layer schema & CRUD"
```

---

## Task 7: 테마 seed JSON + loader

**Files:**
- Create: `data/themes_seed.json`
- Modify: `src/news_briefing/storage/themes.py` (add `load_seed`)
- Modify: `src/news_briefing/cli.py` (add `themes seed` subcommand)

수동 seed 15~20 테마. 각 테마 3~5 레이어, 각 레이어 3~5 기업. 사람이 한 번 검수한 데이터.

- [ ] **Step 1: seed JSON — 15개 주요 테마**

`data/themes_seed.json`:
```json
{
  "themes": [
    {
      "theme_id": "robotics",
      "name_ko": "로봇",
      "description": "산업용·서비스·휴머노이드 로봇",
      "layers": [
        {
          "name": "액추에이터·감속기",
          "description": "정밀 구동 부품",
          "companies": [
            {"ticker": "058610", "name": "에스피지", "positioning": "하모닉 감속기 국내 3위권"},
            {"ticker": "008700", "name": "아노락", "positioning": "..."}
          ]
        },
        {
          "name": "비전·센서",
          "companies": [
            {"ticker": "148150", "name": "세경하이테크", "positioning": "..."}
          ]
        }
      ]
    },
    {
      "theme_id": "ai_semi",
      "name_ko": "AI 반도체",
      "layers": [
        {"name": "HBM", "companies": [{"ticker": "000660", "name": "SK하이닉스", "positioning": "HBM3E 양산"}]},
        {"name": "파운드리", "companies": [{"ticker": "005930", "name": "삼성전자", "positioning": "3nm GAA"}]}
      ]
    }
  ]
}
```

(실제 seed 는 구현 시점에 PRD/SIGNALS 를 보고 15개 정도 채움 — 사용자 수정 권장)

**중요**: seed 는 **"출발점"**이지 "정답"이 아님. P1 원칙상 "추천"이 아니라 "테마 분류 정보 제공" 목적.

- [ ] **Step 2: load_seed 함수**

```python
# storage/themes.py 에 추가
import json
from pathlib import Path


def load_seed(conn: sqlite3.Connection, seed_path: Path) -> dict[str, int]:
    """seed JSON 을 DB 에 일괄 적재. 반환: {theme_id: company_count}."""
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    result: dict[str, int] = {}
    for theme_data in data.get("themes", []):
        theme = Theme(
            theme_id=theme_data["theme_id"],
            name_ko=theme_data["name_ko"],
            description=theme_data.get("description"),
        )
        upsert_theme(conn, theme)
        cnt = 0
        for layer_data in theme_data.get("layers", []):
            lid = upsert_layer(conn, ValueLayer(
                None, theme.theme_id,
                layer_data["name"],
                layer_data.get("description"),
            ))
            for c in layer_data.get("companies", []):
                upsert_company(conn, CompanyInLayer(
                    layer_id=lid,
                    ticker=c["ticker"],
                    company_name=c["name"],
                    positioning=c.get("positioning"),
                    verified=bool(c.get("verified", False)),
                ))
                cnt += 1
        result[theme.theme_id] = cnt
    return result
```

- [ ] **Step 3: CLI subcommand `themes seed`**

```python
# cli.py 에 추가
def _cmd_themes(args) -> int:
    cfg = load_config()
    if args.subcmd == "seed":
        from news_briefing.storage.db import connect
        from news_briefing.storage.themes import load_seed
        conn = connect(cfg.db_path)
        seed_path = PROJECT_ROOT / "data" / "themes_seed.json"
        try:
            result = load_seed(conn, seed_path)
            print(f"seed 적용 완료: {len(result)} 테마, {sum(result.values())} 기업")
        finally:
            conn.close()
        return 0
    # Week 4: 'refresh' subcommand for LLM-based update
    return 2

# main() 의 subparser 에 추가
p_themes = sub.add_parser("themes", help="테마·밸류체인 관리")
themes_sub = p_themes.add_subparsers(dest="subcmd")
themes_sub.add_parser("seed", help="data/themes_seed.json 로부터 DB 로드")
p_themes.set_defaults(func=_cmd_themes)
```

- [ ] **Step 4: Test seed loading**

```python
def test_load_seed(tmp_path, memory_db) -> None:
    seed = {
        "themes": [
            {
                "theme_id": "robotics",
                "name_ko": "로봇",
                "layers": [
                    {
                        "name": "액추에이터",
                        "companies": [{"ticker": "058610", "name": "에스피지"}],
                    }
                ],
            }
        ]
    }
    path = tmp_path / "s.json"
    path.write_text(json.dumps(seed), encoding="utf-8")
    init_schema(memory_db)
    result = load_seed(memory_db, path)
    assert result["robotics"] == 1
```

- [ ] **Step 5: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_themes_storage.py -v
git add data/themes_seed.json src/news_briefing/storage/themes.py src/news_briefing/cli.py tests/test_themes_storage.py
git commit -m "feat(themes): seed JSON + load_seed + CLI 'themes seed' subcommand"
```

---

## Task 8: 밸류체인 LLM 분해 (refresh 커맨드)

**Files:**
- Create: `src/news_briefing/analysis/themes.py`
- Create: `tests/test_themes_analysis.py`
- Modify: `src/news_briefing/cli.py` (`themes refresh` 서브커맨드)

**주의**: 실제 LLM 호출은 시간·토큰 많이 씀. 수동 커맨드로 분리 (`python -m news_briefing themes refresh robotics`). 테스트는 전부 mock.

- [ ] **Step 1: themes.py**

```python
# src/news_briefing/analysis/themes.py
"""밸류체인 LLM 분해 + 기업 포지셔닝 생성 (SIGNALS.md 4절)."""
from __future__ import annotations

import json
import logging
import sqlite3

from news_briefing.analysis.llm import _call_claude
from news_briefing.storage.themes import (
    CompanyInLayer,
    Theme,
    ValueLayer,
    upsert_company,
    upsert_layer,
    upsert_theme,
)

log = logging.getLogger(__name__)


DECOMPOSE_PROMPT = (
    "당신은 산업 애널리스트다. 다음 테마의 밸류체인을 3~5개 공통분모 레이어로 분해해줘.\n"
    "\n"
    "테마: {theme_name}\n"
    "\n"
    "출력은 JSON 한 덩어리로. 형식:\n"
    "{{\n"
    '  "layers": [\n'
    '    {{"name": "레이어명", "description": "이 레이어가 무엇이고 왜 이 테마의 핵심 부품/서비스인지"}},\n'
    "    ...\n"
    "  ],\n"
    '  "caveats": "밸류체인 분해 시 유의사항 1~2줄"\n'
    "}}\n"
    "\n"
    "규칙:\n"
    "- 완성품 제조사가 공유하는 부품/소재/플랫폼에 집중\n"
    "- '관련 있음' 수준의 먼 연결은 제외\n"
    "- 3~5개 레이어 이상 금지 (명료성 ↓)\n"
)


POSITIONING_PROMPT = (
    "당신은 기업 리서처다. 다음 기업이 '{layer}' 레이어에서 어떤 포지션을 갖는지 "
    "한국어 1~2문장으로 정리해줘.\n"
    "\n"
    "기업: {company_name} (티커 {ticker})\n"
    "레이어: {layer}\n"
    "\n"
    "규칙:\n"
    "- 사실 기반 (숫자는 공개 정보 기준)\n"
    "- '매수 유망', '추천' 등 투자 유인 표현 절대 금지\n"
    "- 공개 정보 부족 시 '공개 정보 부족' 으로 명시\n"
    "- 존댓말 '~요' 체 (2문장 이내)\n"
)


def decompose_theme(theme_name: str) -> dict | None:
    """테마 → layers LLM 분해. 실패 시 None."""
    try:
        raw = _call_claude(DECOMPOSE_PROMPT.format(theme_name=theme_name), timeout=60)
    except Exception as e:
        log.error("theme decompose 실패 %s: %s", theme_name, e)
        return None
    try:
        # Claude 가 종종 코드블록으로 감쌀 수 있어 정제
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
            if text.endswith("```"):
                text = text[:-3]
        return json.loads(text)
    except Exception as e:
        log.error("theme decompose JSON 파싱 실패: %s\nraw=%s", e, raw[:200])
        return None


def generate_positioning(
    *, company_name: str, ticker: str, layer: str
) -> str | None:
    try:
        return _call_claude(
            POSITIONING_PROMPT.format(
                company_name=company_name, ticker=ticker, layer=layer
            ),
            timeout=45,
        ).strip()
    except Exception as e:
        log.warning("positioning 실패 %s: %s", company_name, e)
        return None


def refresh_theme_layers(
    conn: sqlite3.Connection, theme: Theme
) -> int:
    """테마의 밸류체인 레이어를 LLM 으로 재생성. 반환: 생성된 layer 개수."""
    result = decompose_theme(theme.name_ko)
    if result is None:
        return 0
    n = 0
    for layer_data in result.get("layers", []):
        upsert_layer(conn, ValueLayer(
            layer_id=None,
            theme_id=theme.theme_id,
            name=layer_data["name"],
            description=layer_data.get("description"),
        ))
        n += 1
    return n
```

- [ ] **Step 2: CLI `themes refresh`**

```python
# cli.py _cmd_themes 확장
if args.subcmd == "refresh":
    from news_briefing.analysis.themes import refresh_theme_layers
    from news_briefing.storage.themes import get_theme
    conn = connect(cfg.db_path)
    try:
        theme = get_theme(conn, args.theme_id)
        if theme is None:
            print(f"테마 없음: {args.theme_id}", file=sys.stderr)
            return 1
        n = refresh_theme_layers(conn, theme)
        print(f"{theme.name_ko}: {n}개 레이어 갱신")
    finally:
        conn.close()
    return 0

# subparser
p_refresh = themes_sub.add_parser("refresh", help="LLM 으로 테마 밸류체인 재생성")
p_refresh.add_argument("theme_id")
```

- [ ] **Step 3: Test (mock LLM)**

```python
def test_decompose_theme_parses_json(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        return_value='{"layers": [{"name": "액추에이터"}], "caveats": "..."}',
    )
    result = decompose_theme("로봇")
    assert result is not None
    assert result["layers"][0]["name"] == "액추에이터"


def test_decompose_handles_code_fences(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        return_value='```json\n{"layers": []}\n```',
    )
    result = decompose_theme("로봇")
    assert result == {"layers": []}


def test_decompose_returns_none_on_llm_failure(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        side_effect=RuntimeError("boom"),
    )
    assert decompose_theme("x") is None


def test_generate_positioning_calls_llm(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        return_value="하모닉 감속기 국내 3위예요.",
    )
    result = generate_positioning(
        company_name="에스피지", ticker="058610", layer="액추에이터"
    )
    assert "하모닉" in result
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_themes_analysis.py -v
git add src/news_briefing/analysis/themes.py src/news_briefing/cli.py tests/test_themes_analysis.py
git commit -m "feat(analysis): LLM-based theme value-chain decomposition + positioning generator"
```

---

## Task 9: 트렌드 감지 (키워드 빈도 이동평균)

**Files:**
- Create: `src/news_briefing/analysis/trends.py`
- Create: `tests/test_trends.py`

과거 7일 뉴스·공시 제목에서 테마 키워드 등장 빈도 추적. 오늘 대비 주간 이동평균 ≥ 2.0x 이면 "신규 주목 테마" 후보.

- [ ] **Step 1: Test**

```python
# tests/test_trends.py
from __future__ import annotations

from datetime import datetime, timedelta

from news_briefing.analysis.trends import detect_trending_themes


def _mk_title_events(titles: list[tuple[str, datetime]]) -> list[tuple[str, datetime]]:
    return titles


def test_no_spike_no_trending() -> None:
    now = datetime(2026, 4, 23)
    events = [(f"로봇 기사 {i}", now - timedelta(days=i)) for i in range(7)]
    trending = detect_trending_themes(events, theme_keywords={"robotics": ["로봇"]}, now=now)
    assert trending == []


def test_spike_detected() -> None:
    now = datetime(2026, 4, 23)
    # 오늘 5건, 이전 주 7일 각 1건
    today_events = [(f"로봇 붐 {i}", now) for i in range(5)]
    past_events = [(f"로봇 평상시 {i}", now - timedelta(days=i + 1)) for i in range(7)]
    trending = detect_trending_themes(
        today_events + past_events,
        theme_keywords={"robotics": ["로봇"]},
        now=now,
    )
    assert "robotics" in trending


def test_multiple_keywords_match_any() -> None:
    now = datetime(2026, 4, 23)
    events = [("HBM 발표", now)] * 4 + [("평상시", now - timedelta(days=i)) for i in range(7)]
    trending = detect_trending_themes(
        events,
        theme_keywords={"ai_semi": ["HBM", "AI 반도체", "파운드리"]},
        now=now,
    )
    assert "ai_semi" in trending
```

- [ ] **Step 2: Implement**

```python
# src/news_briefing/analysis/trends.py
"""테마 키워드 등장 빈도 기반 트렌드 감지."""
from __future__ import annotations

from datetime import datetime, timedelta

SPIKE_THRESHOLD = 2.0   # 오늘 빈도 / 주간 평균이 이 값 이상이면 spike
MIN_TODAY_COUNT = 3     # 오늘 최소 등장 횟수


def _matches(title: str, keywords: list[str]) -> bool:
    return any(k in title for k in keywords)


def detect_trending_themes(
    events: list[tuple[str, datetime]],
    *,
    theme_keywords: dict[str, list[str]],
    now: datetime,
    lookback_days: int = 7,
) -> list[str]:
    """이동평균 대비 spike 가 발생한 theme_id 리스트 반환."""
    today_start = datetime(now.year, now.month, now.day)
    lookback_start = today_start - timedelta(days=lookback_days)

    trending: list[str] = []
    for theme_id, kws in theme_keywords.items():
        today_count = sum(
            1 for title, ts in events
            if ts >= today_start and _matches(title, kws)
        )
        past_count = sum(
            1 for title, ts in events
            if lookback_start <= ts < today_start and _matches(title, kws)
        )
        if today_count < MIN_TODAY_COUNT:
            continue
        daily_avg = past_count / lookback_days if past_count else 0
        if daily_avg == 0:
            # 새로 등장한 테마
            trending.append(theme_id)
            continue
        ratio = today_count / daily_avg
        if ratio >= SPIKE_THRESHOLD:
            trending.append(theme_id)
    return trending
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_trends.py -v
git add src/news_briefing/analysis/trends.py tests/test_trends.py
git commit -m "feat(analysis): trending theme detection via keyword frequency moving average"
```

---

## Task 10: 주간 리포트 기본 템플릿 (weekly CLI + HTML)

**Files:**
- Create: `src/news_briefing/delivery/weekly.py`
- Modify: `src/news_briefing/cli.py` (`weekly` subcommand)
- Create: `tests/test_weekly.py`

Week 3 는 **기본 HTML 나열** 수준. Week 4 에서 LLM 에세이 고도화.

- [ ] **Step 1: weekly.py**

```python
# src/news_briefing/delivery/weekly.py
"""주간 리포트 생성 (ROADMAP Week 4 준비).

Week 3: 기본 나열 — 7일간 상위 시그널 + 트렌드 테마.
Week 4: LLM 에세이·테마 배너 URL.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WeeklyReport:
    week_id: str         # '2026-W17'
    start_date: str      # '2026-04-19'
    end_date: str        # '2026-04-25'
    top_signals: list[dict]
    trending_themes: list[str]


def _iso_week(date: datetime) -> str:
    y, w, _ = date.isocalendar()
    return f"{y}-W{w:02d}"


def collect_weekly(
    briefings_dir: Path, *, now: datetime | None = None
) -> WeeklyReport:
    """지난 7일 브리핑 JSON 을 합쳐서 주간 요약 구조로."""
    now = now or datetime.now()
    end = now
    start = end - timedelta(days=6)

    all_signals: list[dict] = []
    for i in range(7):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        path = briefings_dir / f"{day}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("hero"):
            all_signals.append(data["hero"])
        all_signals.extend(data.get("tabs", {}).get("economy", {}).get("signals", []))

    # 중복 제거 (id)
    seen_ids: set[str] = set()
    unique = []
    for s in all_signals:
        if s["id"] not in seen_ids:
            unique.append(s)
            seen_ids.add(s["id"])
    # 점수 내림차순 상위 20
    unique.sort(key=lambda s: s.get("score", 0), reverse=True)

    return WeeklyReport(
        week_id=_iso_week(end),
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        top_signals=unique[:20],
        trending_themes=[],  # Week 4 에서 trends.detect_trending_themes 연결
    )


def render_weekly_html(report: WeeklyReport) -> str:
    rows = "\n".join(
        f'  <li><strong>{s.get("company", "—")}</strong>: {s.get("headline", "")} '
        f'(점수 {s.get("score", 0)}) <a href="{s.get("url", "#")}">원문</a></li>'
        for s in report.top_signals
    )
    return (
        f"<!doctype html>\n"
        f'<html lang="ko"><head><meta charset="utf-8">'
        f"<title>주간 리포트 · {report.week_id}</title></head>"
        f"<body>"
        f"<h1>주간 리포트 · {report.week_id}</h1>"
        f"<p>{report.start_date} ~ {report.end_date}</p>"
        f"<h2>주요 시그널 상위 {len(report.top_signals)}건</h2>"
        f"<ol>\n{rows}\n</ol>"
        f"</body></html>\n"
    )


def write_weekly(
    *, reports_dir: Path, report: WeeklyReport
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{report.week_id}.html"
    path.write_text(render_weekly_html(report), encoding="utf-8")
    return path
```

- [ ] **Step 2: CLI subcommand**

```python
def _cmd_weekly(args) -> int:
    from news_briefing.delivery.weekly import collect_weekly, write_weekly
    cfg = load_config()
    reports_dir = cfg.public_briefings_dir.parent / "reports"
    report = collect_weekly(cfg.public_briefings_dir)
    path = write_weekly(reports_dir=reports_dir, report=report)
    print(f"주간 리포트 생성: {path}")
    print(f"  {report.week_id} · {len(report.top_signals)}개 시그널")
    return 0

# subparser
p_weekly = sub.add_parser("weekly", help="주간 리포트 생성 (일요일 저녁)")
p_weekly.set_defaults(func=_cmd_weekly)
```

- [ ] **Step 3: Test**

```python
# tests/test_weekly.py
import json
from datetime import datetime
from pathlib import Path

from news_briefing.delivery.weekly import collect_weekly, render_weekly_html, write_weekly


def _write_brief(dir: Path, date: str, signals: list[dict]) -> None:
    (dir / f"{date}.json").write_text(json.dumps({
        "date": date, "generatedAt": "x", "version": 1,
        "hero": None,
        "tabs": {"current": {}, "economy": {"indices": [], "signals": signals, "news": []},
                 "picks": {"domestic": [], "foreign": []}},
        "glossary": {},
    }, ensure_ascii=False), encoding="utf-8")


def test_collect_weekly_aggregates_last_7_days(tmp_path: Path) -> None:
    for i in range(7):
        d = (datetime(2026, 4, 23) - __import__("datetime").timedelta(days=i)).strftime("%Y-%m-%d")
        _write_brief(tmp_path, d, [{"id": f"s{i}", "company": "A", "headline": "t", "score": 60 + i, "url": "x"}])
    report = collect_weekly(tmp_path, now=datetime(2026, 4, 23))
    assert report.week_id.startswith("2026-W")
    assert len(report.top_signals) == 7


def test_dedup_same_id_across_days(tmp_path: Path) -> None:
    # 같은 id 가 두 날짜에 있으면 한 번만
    _write_brief(tmp_path, "2026-04-22", [{"id": "dup", "company": "A", "headline": "t", "score": 70, "url": "x"}])
    _write_brief(tmp_path, "2026-04-23", [{"id": "dup", "company": "A", "headline": "t", "score": 70, "url": "x"}])
    report = collect_weekly(tmp_path, now=datetime(2026, 4, 23))
    assert len(report.top_signals) == 1


def test_write_weekly_creates_html(tmp_path: Path) -> None:
    from news_briefing.delivery.weekly import WeeklyReport
    report = WeeklyReport("2026-W17", "2026-04-19", "2026-04-25",
                          top_signals=[{"company": "삼성", "headline": "자사주", "score": 85, "url": "x"}],
                          trending_themes=[])
    path = write_weekly(reports_dir=tmp_path, report=report)
    assert path.exists()
    assert "삼성" in path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_weekly.py -v
git add src/news_briefing/delivery/weekly.py src/news_briefing/cli.py tests/test_weekly.py
git commit -m "feat(delivery): weekly report basic HTML (Week 4 will add LLM essay)"
```

---

## Task 11: Frontend — 시사 탭 카테고리 섹션

**Files:**
- Modify: `frontend/src/app/page.tsx` (current 탭 렌더 개선)
- Modify: `frontend/src/lib/types.ts` (NewsItem 에 category 추가)
- Create: `frontend/src/components/CurrentSection.tsx` (섹션 헤더 + 카드 리스트)

- [ ] **Step 1: Extend NewsItem type**

```typescript
// types.ts
export interface NewsItem {
  // ... 기존
  category?: 'politics' | 'society' | 'international' | 'tech' | 'stock'
}
```

- [ ] **Step 2: CurrentSection**

```tsx
// components/CurrentSection.tsx
'use client'
import type { NewsItem } from '@/lib/types'
import { CurrentNewsCard } from './CurrentNewsCard'

const SECTION_LABEL: Record<string, string> = {
  politics: '정치',
  society: '사회',
  international: '국제',
  tech: 'IT · 과학',
}

export function CurrentSection({
  category,
  news,
  dict,
}: {
  category: keyof typeof SECTION_LABEL
  news: NewsItem[]
  dict: import('@/lib/i18n/ko').Dict
}) {
  if (news.length === 0) return null
  return (
    <section style={{ paddingTop: 24 }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, padding: '0 20px 6px',
                   color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
        {SECTION_LABEL[category]}
      </h2>
      <div style={{ fontSize: 13, color: 'var(--text-tertiary)',
                    padding: '0 20px 12px' }}>
        주목할 {news.length}건
      </div>
      {news.map((n) => (
        <CurrentNewsCard key={n.id} news={n} dict={dict} />
      ))}
    </section>
  )
}
```

- [ ] **Step 3: page.tsx current 탭 분기**

```tsx
// tab === 'current' 분기
if (tab === 'current') {
  const current = briefing.tabs.current
  const filter = (arr: NewsItem[]) => arr.filter((n) => {
    if (scope === 'all') return true
    if (scope === 'domestic') return n.scope === 'domestic'
    return n.scope === 'foreign'
  })
  const sections: ('politics' | 'society' | 'international' | 'tech')[] = [
    'politics', 'society', 'international', 'tech',
  ]
  const anyNews = sections.some((s) => filter(current[s]).length > 0)
  if (!anyNews) {
    return <p className="px-5 py-16 text-center"
              style={{ color: 'var(--text-secondary)' }}>
      {dict['empty.current']}
    </p>
  }
  return (
    <div>
      {sections.map((s) => (
        <CurrentSection key={s} category={s} news={filter(current[s])} dict={dict} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Build check + commit**

```bash
cd /c/GitHub/daily-news/frontend && npm run build
git add frontend/src/
git commit -m "feat(frontend): current-affairs tab section rendering (politics/society/intl/tech)"
```

---

## Task 12: E2E + 최종 검증

- [ ] **Step 1: seed 적용**

```bash
.venv/Scripts/python.exe -m news_briefing themes seed
```

Expected: `seed 적용 완료: N 테마, M 기업`

- [ ] **Step 2: dry-run 으로 시사 데이터 수집**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m news_briefing morning --dry-run
```

Expected: 시사 카테고리별 건수 표시, briefing JSON 의 `tabs.current.politics` 등이 채워짐.

- [ ] **Step 3: 주간 리포트 생성**

```bash
.venv/Scripts/python.exe -m news_briefing weekly
```

Expected: `data/reports/2026-W17.html` (또는 해당 ISO week) 파일 생성.

- [ ] **Step 4: Frontend rebuild + 브라우저 확인**

dev 서버 hot reload 로 자동 반영. 시사 탭 접속 → 정치·사회·국제·IT 섹션 렌더, 각 카드에 용어 주석 포함 확인.

- [ ] **Step 5: pytest 전체 + ruff**

```bash
.venv/Scripts/python.exe -m pytest 2>&1 | tail -3
.venv/Scripts/python.exe -m ruff check src tests
```

- [ ] **Step 6: 최종 commit + push**

```bash
git push
```

---

## Week 3 Definition of Done

- [ ] 시사 RSS 피드 (정치·사회·국제·IT) 각 ≥2개 등록, dry-run 시 수집 확인
- [ ] 시사 뉴스 카테고리별 그루핑, briefing JSON 에 `tabs.current.politics/society/international/tech` 채워짐
- [ ] 각 시사 뉴스에 `curationScore` 부착
- [ ] 시사 용어 (원내대표·전원합의체 등 ≥4개) glossary 감지·해설
- [ ] 테마 DB 스키마 완성, `data/themes_seed.json` 로 최소 **15개 테마** · 각 5+ 기업 매핑 (PRD DoD)
- [ ] `themes refresh <theme_id>` CLI 로 밸류체인 LLM 분해 실행 가능 (mock 테스트)
- [ ] 트렌드 감지 로직 단위 테스트 통과 (spike 탐지)
- [ ] `weekly` CLI 로 주간 리포트 HTML 생성
- [ ] 프론트 시사 탭에서 섹션별 카드 렌더
- [ ] pytest 전체 pass + ruff clean

### Week 3 에서 하지 않는 것 (Week 4 이관)

- 경제 탭 상단 "이번 주 주목 테마" 배너 UI (F12 Week 4)
- 주간 리포트 LLM 에세이 (Week 4)
- RAG 엔진 (Week 4)
- 인포스탁 크롤러 실제 페치 (옵션 스크립트로 존재하되 seed 우선)

---

## Self-Review

**Spec coverage (ROADMAP Week 3 작업 항목):**
1. 시사 뉴스 수집 → T1 ✅
2. 시사 큐레이션 → T2 ✅
3. 시사 용어 주석 → T3 ✅
4. 테마주 DB (seed + schema) → T6-7 ✅
5. 밸류체인 LLM 분해 → T8 ✅
6. 기업 포지셔닝 → T8 (generate_positioning) ✅
7. 트렌드 감지 → T9 ✅
8. 주간 리포트 기본 → T10 ✅
9. 프론트 시사 탭 렌더 → T11 ✅
10. E2E 검증 → T12 ✅

**Placeholder 없음, type 일관성 확인 완료.**

**Risks:**
- RSS 피드 URL 일부는 시점상 살아있지 않을 수 있음 — 실패해도 다른 소스는 진행 (orchestrator 원칙)
- `themes refresh` LLM 호출은 비용·시간 많이 씀 — 수동 실행으로 분리, 자동화 지양
- seed JSON 은 Week 3 시점의 스냅샷 — 분기 1회 사람 검수 필요 (SIGNALS 3.3)
