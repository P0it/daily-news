# Week 2a: PWA 기반 + 시사/경제 2탭 + 해설 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Week 1 MVP 위에 설치 가능한 PWA 앱 셸을 올린다. Next.js 15 static export + Tailwind + 디자인 시스템 + 시사/경제 2탭 (3탭은 Week 2b) + 용어 주석 엔진 + 시그널 스코어링 v2 + 다크모드 + i18n 기반 + 카톡 링크 방식까지.

**Architecture:** 백엔드는 Week 1 을 확장해 `storage/glossary.py` · `analysis/glossary.py` · `delivery/json_builder.py` 추가. 프론트엔드는 신규 `frontend/` 디렉토리에 Next.js 15 static export (TypeScript + Tailwind + App Router). 백엔드가 매 morning 실행 시 `frontend/public/briefings/YYYY-MM-DD.json` 파일을 쓰고, 프론트엔드는 빌드 타임에 이 디렉토리를 정적 파일로 export 한다. PWA 는 custom service worker + manifest.json. 카톡 메시지는 Vercel URL 링크 방식으로 전환.

**Tech Stack:** 백엔드 Week 1 그대로 + `pillow` (아이콘 생성). 프론트엔드 Next.js 15 + React 19 + TypeScript 5 + Tailwind CSS 4 + Pretendard Variable (CDN) + 커스텀 service worker (vanilla, workbox 미사용).

**Platform note:** 프론트엔드도 Windows 개발 + Vercel(클라우드) 배포. 로컬 검증은 `npm run dev` + `next build && next export`. 실제 배포 URL 검증은 사용자 GitHub push + Vercel 연결 후.

---

## File Structure (Week 2a 결과물)

### 백엔드 (Python)

| 파일 | 책임 |
|------|------|
| `src/news_briefing/storage/glossary.py` | glossary 테이블 read/write |
| `src/news_briefing/analysis/glossary.py` | 공시 제목 → 용어 감지 + LLM 해설 lazy 생성 |
| `src/news_briefing/analysis/scoring.py` (수정) | v2 정량 보정 — 금액·지분율·매수/매도 구분 |
| `src/news_briefing/delivery/json_builder.py` | `Briefing` JSON 스키마로 export |
| `src/news_briefing/orchestrator.py` (수정) | JSON 생성 단계 추가, 카톡 링크 포맷 |
| `src/news_briefing/storage/db.py` (수정) | glossary 테이블 스키마 추가 |

### 프론트엔드 (Next.js 15)

| 파일 | 책임 |
|------|------|
| `frontend/package.json` | 의존성 |
| `frontend/next.config.mjs` | static export 설정 |
| `frontend/tailwind.config.ts` | DESIGN.md 토큰 |
| `frontend/postcss.config.mjs` | Tailwind postcss |
| `frontend/tsconfig.json` | TypeScript 설정 |
| `frontend/src/app/layout.tsx` | 앱 셸 (HTML · 헤더 · TabBar) |
| `frontend/src/app/page.tsx` | 오늘 브리핑 (기본 라우트) |
| `frontend/src/app/[date]/page.tsx` | 날짜별 브리핑 |
| `frontend/src/app/globals.css` | Tailwind import + CSS variables |
| `frontend/src/components/TabBar.tsx` | pill segmented (2탭) |
| `frontend/src/components/ScopeFilter.tsx` | text + underline (국내/해외) |
| `frontend/src/components/HeroCard.tsx` | 오늘 가장 중요한 1건 |
| `frontend/src/components/SignalCard.tsx` | 일반 시그널 카드 |
| `frontend/src/components/CurrentNewsCard.tsx` | 시사 뉴스 카드 |
| `frontend/src/components/MarketIndices.tsx` | 3분할 지표 |
| `frontend/src/components/GlossaryPopover.tsx` | 용어 해설 inset + 펼침 |
| `frontend/src/components/InstallPrompt.tsx` | PWA 설치 배너 |
| `frontend/src/components/ThemeToggle.tsx` | 다크 모드 토글 |
| `frontend/src/components/LangToggle.tsx` | KO/EN 토글 |
| `frontend/src/lib/fetchBriefing.ts` | JSON 로드 + 에러 처리 |
| `frontend/src/lib/types.ts` | Briefing, SignalItem 등 TypeScript 타입 |
| `frontend/src/lib/i18n.ts` | 정적 사전 ko/en 전환 |
| `frontend/src/lib/theme.ts` | 다크모드 local storage helper |
| `frontend/src/lib/tabs.ts` | 탭 상태 + URL 쿼리 동기화 |
| `frontend/public/manifest.json` | PWA manifest |
| `frontend/public/sw.js` | service worker (cache-first 앱 셸, network-first JSON) |
| `frontend/public/icons/icon-192.png` | PWA 아이콘 |
| `frontend/public/icons/icon-512.png` | PWA 아이콘 |
| `frontend/public/icons/apple-touch-icon.png` | iOS |
| `scripts/generate_icons.py` | placeholder 아이콘 생성 |

### 테스트

| 파일 | 책임 |
|------|------|
| `tests/test_scoring_v2.py` | 정량 보정 검증 |
| `tests/test_glossary.py` | 용어 감지 + 캐시 |
| `tests/test_json_builder.py` | 스키마 검증 |
| `tests/test_orchestrator_v2.py` | 2a morning 통합 |

---

## Task 1: Backend — scoring v2 정량 보정

**Files:**
- Modify: `src/news_briefing/analysis/scoring.py`
- Create: `tests/test_scoring_v2.py`

`SIGNALS.md` 2.3 정량 보정 (금액·지분율·매수매도 구분) 을 기본 점수에 더한다. Week 1 의 `score_report(report_name)` 는 유지하고, 새 함수 `score_with_context(report_name, ctx)` 를 추가.

- [ ] **Step 1: Failing test**

```python
# tests/test_scoring_v2.py
from __future__ import annotations

from news_briefing.analysis.scoring import score_with_context, ScoringContext


def test_self_stock_buyback_scaled_by_amount() -> None:
    """자기주식취득 규모가 시총 1% 이상이면 +10, 5% 이상이면 +25."""
    small = score_with_context(
        "자기주식취득결정", ScoringContext(amount=1_000_000_000, market_cap=1_000_000_000_000)
    )
    large = score_with_context(
        "자기주식취득결정", ScoringContext(amount=60_000_000_000, market_cap=1_000_000_000_000)
    )
    huge = score_with_context(
        "자기주식취득결정", ScoringContext(amount=100_000_000_000, market_cap=1_000_000_000_000)
    )
    assert small.score == 80       # base
    assert large.score == 80 + 10  # 6% of cap → +10 (1%+)
    assert huge.score == 80 + 25   # 10% of cap → +25 (5%+)


def test_self_stock_buyback_market_purchase_bonus() -> None:
    """장내매수가 신탁보다 강한 신호."""
    tr = score_with_context(
        "자기주식취득결정", ScoringContext(acquisition_method="신탁")
    )
    mkt = score_with_context(
        "자기주식취득결정", ScoringContext(acquisition_method="장내매수")
    )
    assert mkt.score == tr.score + 5


def test_insider_trade_buy_vs_sell_direction() -> None:
    """임원·주요주주 공시는 매수/매도로 방향성 분기."""
    buy = score_with_context(
        "임원ㆍ주요주주특정증권등소유상황보고서",
        ScoringContext(trade_type="매수", is_ceo=True, amount=2_000_000_000),
    )
    sell = score_with_context(
        "임원ㆍ주요주주특정증권등소유상황보고서",
        ScoringContext(trade_type="매도", stake_change_pct=2.0),
    )
    assert buy.direction == "positive"
    assert sell.direction == "negative"
    assert buy.score == 70 + 15 + 10  # CEO + 10억 초과
    assert sell.score == 70 + 15  # 지분율 1% 초과


def test_empty_context_matches_v1_behavior() -> None:
    """컨텍스트 없으면 v1 점수와 동일."""
    r = score_with_context("자기주식취득결정", ScoringContext())
    assert r.score == 80
    assert r.direction == "positive"


def test_scoring_result_clamps_at_100() -> None:
    r = score_with_context(
        "자기주식취득결정",
        ScoringContext(amount=500_000_000_000, market_cap=1_000_000_000_000,
                       acquisition_method="장내매수"),
    )
    assert r.score <= 100
```

- [ ] **Step 2: Run failing**

```bash
.venv/Scripts/python.exe -m pytest tests/test_scoring_v2.py -v
```

- [ ] **Step 3: Extend scoring.py**

```python
# 추가할 dataclass + 함수 (기존 내용 아래에)
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScoringContext:
    amount: int | None = None              # 원 단위 (공시 금액)
    market_cap: int | None = None          # 원 단위 (시가총액)
    acquisition_method: str | None = None  # '장내매수' | '신탁' | 기타
    trade_type: str | None = None          # '매수' | '매도' (임원공시)
    stake_change_pct: float | None = None  # 지분율 변동 %
    is_ceo: bool = False                   # CEO / 등기임원 여부
    is_largest_shareholder: bool = False   # 최대주주 여부


@dataclass(frozen=True, slots=True)
class ScoringResult:
    score: int
    direction: Direction


def score_with_context(report_name: str, ctx: ScoringContext) -> ScoringResult:
    base_score, direction = score_report(report_name)
    bonus = 0

    # 자기주식취득 정량 보정
    if "자기주식취득" in report_name:
        if ctx.amount and ctx.market_cap:
            ratio = ctx.amount / ctx.market_cap
            if ratio >= 0.05:
                bonus += 25
            elif ratio >= 0.01:
                bonus += 10
        if ctx.acquisition_method == "장내매수":
            bonus += 5

    # 임원·주요주주 매수/매도
    if "임원" in report_name and "주주" in report_name:
        if ctx.trade_type == "매수":
            direction = "positive"
            if ctx.is_ceo:
                bonus += 15
            if ctx.amount and ctx.amount > 1_000_000_000:
                bonus += 10
        elif ctx.trade_type == "매도":
            direction = "negative"
            if ctx.stake_change_pct and ctx.stake_change_pct > 1.0:
                bonus += 15
            if ctx.is_largest_shareholder:
                bonus += 20

    final = min(100, base_score + bonus)
    return ScoringResult(score=final, direction=direction)
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_scoring_v2.py tests/test_scoring.py -v
git add src/news_briefing/analysis/scoring.py tests/test_scoring_v2.py
git commit -m "feat(analysis): signal scoring v2 with amount/stake/trade quantitative boost"
```

---

## Task 2: Backend — glossary table + storage helpers

**Files:**
- Modify: `src/news_briefing/storage/db.py` (add glossary schema)
- Create: `src/news_briefing/storage/glossary.py`
- Create: `tests/test_glossary_storage.py`

- [ ] **Step 1: Extend db.py schema**

```python
# src/news_briefing/storage/db.py 의 _SCHEMA 에 추가:
_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (...);
CREATE INDEX IF NOT EXISTS idx_seen_time ON seen(seen_at);

CREATE TABLE IF NOT EXISTS llm_cache (...);

CREATE TABLE IF NOT EXISTS glossary (
    term_id         TEXT NOT NULL,
    lang            TEXT NOT NULL DEFAULT 'ko',
    short_label     TEXT NOT NULL,
    explanation     TEXT NOT NULL,
    signal_direction TEXT,
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (term_id, lang)
);
"""
```

- [ ] **Step 2: Failing test**

```python
# tests/test_glossary_storage.py
from __future__ import annotations

import sqlite3

from news_briefing.storage.db import init_schema
from news_briefing.storage.glossary import (
    get_glossary_entry,
    upsert_glossary_entry,
    GlossaryEntry,
)


def test_roundtrip(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    entry = GlossaryEntry(
        term_id="self_stock_buy",
        lang="ko",
        short_label="자사주 매수",
        explanation="회사가 자기 주식을 사는 결정이에요.",
        signal_direction="positive",
    )
    upsert_glossary_entry(memory_db, entry)
    got = get_glossary_entry(memory_db, "self_stock_buy", "ko")
    assert got == entry


def test_miss_returns_none(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert get_glossary_entry(memory_db, "unknown", "ko") is None


def test_language_separation(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    ko = GlossaryEntry("self_stock_buy", "ko", "자사주 매수", "한국어", "positive")
    en = GlossaryEntry("self_stock_buy", "en", "Share Buyback", "English", "positive")
    upsert_glossary_entry(memory_db, ko)
    upsert_glossary_entry(memory_db, en)
    assert get_glossary_entry(memory_db, "self_stock_buy", "ko").explanation == "한국어"
    assert get_glossary_entry(memory_db, "self_stock_buy", "en").explanation == "English"


def test_upsert_updates_explanation(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_glossary_entry(
        memory_db,
        GlossaryEntry("x", "ko", "라벨", "구 설명", "neutral"),
    )
    upsert_glossary_entry(
        memory_db,
        GlossaryEntry("x", "ko", "라벨2", "신 설명", "positive"),
    )
    got = get_glossary_entry(memory_db, "x", "ko")
    assert got.explanation == "신 설명"
    assert got.short_label == "라벨2"
```

- [ ] **Step 3: Implement storage/glossary.py**

```python
# src/news_briefing/storage/glossary.py
"""용어 해설 (glossary) 테이블 read/write."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    term_id: str
    lang: str
    short_label: str
    explanation: str
    signal_direction: str | None


def get_glossary_entry(
    conn: sqlite3.Connection, term_id: str, lang: str
) -> GlossaryEntry | None:
    row = conn.execute(
        "SELECT term_id, lang, short_label, explanation, signal_direction "
        "FROM glossary WHERE term_id = ? AND lang = ?",
        (term_id, lang),
    ).fetchone()
    if row is None:
        return None
    return GlossaryEntry(
        term_id=row["term_id"],
        lang=row["lang"],
        short_label=row["short_label"],
        explanation=row["explanation"],
        signal_direction=row["signal_direction"],
    )


def upsert_glossary_entry(conn: sqlite3.Connection, entry: GlossaryEntry) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO glossary"
        "(term_id, lang, short_label, explanation, signal_direction, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            entry.term_id,
            entry.lang,
            entry.short_label,
            entry.explanation,
            entry.signal_direction,
            now,
        ),
    )
    conn.commit()
```

- [ ] **Step 4: Update db.py**

Edit `_SCHEMA` to append the glossary CREATE TABLE.

- [ ] **Step 5: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_glossary_storage.py tests/test_db.py -v
git add src/news_briefing/storage/db.py src/news_briefing/storage/glossary.py tests/test_glossary_storage.py
git commit -m "feat(storage): glossary table with ko/en language separation"
```

---

## Task 3: Backend — glossary term detection + LLM generation

**Files:**
- Create: `src/news_briefing/analysis/glossary.py`
- Create: `tests/test_glossary_analysis.py`

공시 제목 → `term_id` 매핑 + 해설이 없으면 LLM 호출해 생성 후 DB 저장. `SIGNALS.md` 3.2 의 예시 해설을 기본 catalog 으로.

- [ ] **Step 1: Failing tests**

```python
# tests/test_glossary_analysis.py
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
    # SIGNALS.md 3.2 기준 최소 7개 (자사주매수 / 내부자매매 / 유상증자 / 감자 / 단일판매 / 잠정실적 / 최대주주변경)
    assert len(TERM_CATALOG) >= 7


def test_ensure_glossary_uses_seed_when_defined(memory_db: sqlite3.Connection) -> None:
    """seed 에 있는 용어는 LLM 호출 없이 바로 DB 에 심어진다."""
    init_schema(memory_db)
    entry = ensure_glossary_entry(memory_db, "self_stock_buy", lang="ko")
    assert entry is not None
    assert "자사주" in entry.short_label or "자기주식" in entry.short_label
    # 캐시됐는지
    cached = get_glossary_entry(memory_db, "self_stock_buy", "ko")
    assert cached == entry


def test_ensure_glossary_falls_back_to_llm_for_unseeded_term(
    memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    # 존재하지 않는 term_id 를 임시로 TERM_CATALOG 에 추가 (seed 없음)
    TERM_CATALOG["_test_term"] = ("_test_term", "테스트용어")

    mock_llm = mocker.patch(
        "news_briefing.analysis.glossary._generate_explanation_via_llm",
        return_value=("테스트용어", "LLM 생성 해설", "neutral"),
    )
    try:
        entry = ensure_glossary_entry(memory_db, "_test_term", lang="ko")
        assert mock_llm.call_count == 1
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
    # seed 용어는 첫 호출에서 seed 로 심어지고, 두 번째 호출은 캐시 히트
    ensure_glossary_entry(memory_db, "self_stock_buy", lang="ko")
    ensure_glossary_entry(memory_db, "self_stock_buy", lang="ko")
    assert mock_llm.call_count == 0
```

- [ ] **Step 2: Run failing**

- [ ] **Step 3: Implement analysis/glossary.py**

```python
# src/news_briefing/analysis/glossary.py
"""용어 해설 엔진.

공시 제목 → term_id 매핑 + seed 카탈로그 + LLM lazy 생성.
SIGNALS.md 3.2 예시를 seed 로 사용.
"""
from __future__ import annotations

import logging
import sqlite3

from news_briefing.analysis.llm import _call_claude, _call_ollama
from news_briefing.storage.glossary import GlossaryEntry, get_glossary_entry, upsert_glossary_entry

log = logging.getLogger(__name__)


# term_id → (short_label_hint, keyword_for_detection)
TERM_CATALOG: dict[str, tuple[str, str]] = {
    "self_stock_buy": ("자사주 매수", "자기주식취득"),
    "self_stock_sell": ("자사주 처분", "자기주식처분"),
    "insider_trade": ("내부자 매매", "임원ㆍ주요주주"),
    "rights_offering": ("유상증자", "유상증자"),
    "capital_reduction": ("감자", "감자결정"),
    "big_contract": ("대형 수주", "단일판매"),
    "tentative_earnings": ("잠정 실적", "영업(잠정)실적"),
    "largest_shareholder_change": ("최대주주 변경", "최대주주변경"),
    "convertible_bond": ("전환사채 발행", "전환사채"),
    "merger": ("합병", "합병"),
    "embezzlement": ("횡령·배임", "횡령"),
    "management_watch": ("관리종목 지정", "관리종목지정"),
}


# SIGNALS.md 3.2 에 적힌 해설을 seed 로
SEED_EXPLANATIONS_KO: dict[str, tuple[str, str, str]] = {
    # term_id → (short_label, explanation, direction)
    "self_stock_buy": (
        "자사주 매수",
        "회사가 자기 주식을 사들이는 결정이에요. 보통 주주 환원이나 주가 방어 목적으로 해요. "
        "매수한 주식을 소각(영구 소멸)하면 주당 가치가 즉시 개선돼서 통상 긍정 신호로 봐요.",
        "positive",
    ),
    "insider_trade": (
        "내부자 매매",
        "회사 임원이나 5% 이상 주요주주가 자사 주식을 사고팔면 5영업일 내에 공시해요. "
        "내부 정보에 밝은 사람의 거래라서 시장이 주목해요. "
        "매수는 '저평가로 본다', 매도는 '차익 실현 또는 부정 전망'으로 통상 해석해요.",
        "mixed",
    ),
    "rights_offering": (
        "유상증자",
        "회사가 새 주식을 발행해 돈을 조달하는 결정이에요. "
        "성장 자금이라는 긍정면과 기존 주주 지분 희석이라는 부정면이 같이 있어요. "
        "'생산설비 투자'면 덜 부정적, '운영자금'이면 부정적으로 통상 해석해요.",
        "mixed",
    ),
    "capital_reduction": (
        "감자 (자본 감소)",
        "회사가 발행 주식 수를 줄이는 결정이에요. "
        "무상감자는 결손 정리(대개 부정), 유상감자는 과잉 자본 반환(중립~긍정)으로 해석해요. "
        "무상감자는 주가 급락 빈도가 높아요.",
        "negative",
    ),
    "big_contract": (
        "대형 수주",
        "매출 10% 이상 규모의 단일 공급계약이 체결되면 공시 의무가 있어요. "
        "신규 매출 가시성을 주는 긍정 신호로 해석해요. "
        "계약 금액·상대방·기간이 핵심이에요. 체결 후 취소도 종종 있어요.",
        "positive",
    ),
    "tentative_earnings": (
        "잠정 실적",
        "분기 종료 후 약 1개월 안에 잠정 영업이익·매출을 발표해요. "
        "애널리스트 컨센서스 대비 서프라이즈/쇼크 여부가 핵심이에요. "
        "확정 실적은 분기보고서에서 다시 확인돼요.",
        "mixed",
    ),
    "largest_shareholder_change": (
        "최대주주 변경",
        "회사 경영권을 가진 대주주가 바뀌는 이벤트예요. "
        "M&A·상속·재무구조 개선 등 배경이 다양해요. "
        "변경 사유와 인수 주체에 따라 해석이 크게 달라져요.",
        "mixed",
    ),
    "convertible_bond": (
        "전환사채 발행",
        "일정 조건에서 주식으로 전환할 수 있는 채권을 발행하는 결정이에요. "
        "자금 조달은 긍정이지만 전환 시 지분 희석이 따라와요. "
        "전환가·전환조건이 핵심 변수예요.",
        "mixed",
    ),
    "merger": (
        "합병",
        "두 회사가 하나로 합쳐지는 결정이에요. "
        "시너지 기대와 지분 희석·경영권 이슈가 같이 있어요. "
        "합병비율과 인수 주체의 성격이 해석을 좌우해요.",
        "mixed",
    ),
    "embezzlement": (
        "횡령·배임",
        "회사 임원이 직책을 이용해 자금을 빼돌리거나 손해를 끼치는 행위예요. "
        "거래정지로 이어질 수 있어서 시장이 가장 예민해요. "
        "금액 규모와 관여자 직급이 핵심이에요.",
        "negative",
    ),
    "management_watch": (
        "관리종목 지정",
        "상장폐지 요건에 근접한 기업으로 지정되는 상태예요. "
        "재무·감사·공시 문제 등 원인이 다양해요. "
        "해제되면 관리종목에서 벗어나요.",
        "negative",
    ),
    "self_stock_sell": (
        "자사주 처분",
        "회사가 보유 중이던 자사주를 팔거나 직원 보상(ESOP)에 쓰는 결정이에요. "
        "매각이면 수급상 부담, ESOP면 중립~긍정으로 해석이 갈려요. "
        "처분 방식과 사유가 핵심이에요.",
        "mixed",
    ),
}


def detect_term(report_name: str) -> str | None:
    """공시 제목에서 term_id 를 추출. 우선순위대로 매칭."""
    for term_id, (_label, keyword) in TERM_CATALOG.items():
        if keyword in report_name:
            return term_id
    return None


def _generate_explanation_via_llm(
    term_id: str, short_label_hint: str, lang: str
) -> tuple[str, str, str]:
    """LLM 으로 해설 생성. 실패 시 (short_label_hint, "", "neutral") 반환.

    Returns (short_label, explanation, direction)
    """
    prompt = (
        f"공시 용어 '{short_label_hint}' ({term_id}) 를 주식 초심자에게 "
        f"{lang} 로 설명해줘. "
        "형식: 1) 한 줄 별칭 (일상어) 2) 3~4줄 해설 3) 주의 한 줄. "
        "'사세요/파세요' 같은 권유 금지. '~요' 존댓말. "
        "첫 줄은 '라벨: ', 두 번째 단락은 '해설: ', 마지막은 '방향: positive|negative|mixed|neutral' 형식."
    )
    try:
        raw = _call_claude(prompt, timeout=45)
    except Exception as e:
        log.warning("glossary LLM 실패 %s: %s", term_id, e)
        return short_label_hint, "", "neutral"

    # 간단 파싱
    label = short_label_hint
    explanation = raw
    direction = "neutral"
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("라벨:"):
            label = line.split(":", 1)[1].strip()
        elif line.startswith("방향:"):
            direction = line.split(":", 1)[1].strip()
    # 해설은 "해설:" 이후 부분
    if "해설:" in raw:
        explanation = raw.split("해설:", 1)[1].strip()

    return label, explanation, direction if direction in (
        "positive", "negative", "mixed", "neutral"
    ) else "neutral"


def ensure_glossary_entry(
    conn: sqlite3.Connection, term_id: str, lang: str = "ko"
) -> GlossaryEntry | None:
    """DB 에서 term_id 해설을 반환. 없으면 seed 또는 LLM 으로 채운 뒤 반환."""
    cached = get_glossary_entry(conn, term_id, lang)
    if cached is not None:
        return cached

    if term_id not in TERM_CATALOG:
        log.warning("unknown term_id=%s", term_id)
        return None

    short_label_hint = TERM_CATALOG[term_id][0]

    # 1. seed 사전 우선 (한국어만)
    if lang == "ko" and term_id in SEED_EXPLANATIONS_KO:
        label, explanation, direction = SEED_EXPLANATIONS_KO[term_id]
    else:
        # 2. LLM fallback
        label, explanation, direction = _generate_explanation_via_llm(
            term_id, short_label_hint, lang
        )

    if not explanation:
        return None

    entry = GlossaryEntry(
        term_id=term_id,
        lang=lang,
        short_label=label,
        explanation=explanation,
        signal_direction=direction,
    )
    upsert_glossary_entry(conn, entry)
    return entry
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_glossary_analysis.py -v
git add src/news_briefing/analysis/glossary.py tests/test_glossary_analysis.py
git commit -m "feat(analysis): glossary term detection + seed catalog + LLM fallback"
```

---

## Task 4: Backend — JSON builder

**Files:**
- Create: `src/news_briefing/delivery/json_builder.py`
- Create: `tests/test_json_builder.py`

`ARCHITECTURE.md` 6.4 Briefing 스키마로 export. Week 2a 에서는 `tabs.current` + `tabs.economy` 만. `tabs.picks` 는 Week 2b.

- [ ] **Step 1: Failing test**

```python
# tests/test_json_builder.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem
from news_briefing.delivery.json_builder import build_briefing_json, write_briefing


def _item(title="공시", ext_id="x") -> CollectedItem:
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
    assert "version" in data
    assert data["hero"] is None
    assert "current" in data["tabs"]
    assert "economy" in data["tabs"]


def test_hero_set_when_score_above_90() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 22),
        scored_signals=[(_item("횡령"), 95, "negative")],
        economy_news=[],
    )
    assert data["hero"] is not None
    assert data["hero"]["score"] == 95


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
    assert scores == [80]  # 60 미만 제외


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
```

- [ ] **Step 2: Implement json_builder.py**

```python
# src/news_briefing/delivery/json_builder.py
"""Briefing JSON 생성 + frontend/public/briefings 에 기록.

ARCHITECTURE.md 6.4 스키마 준수.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem

SCHEMA_VERSION = 1
HERO_THRESHOLD = 90
ECONOMY_SIGNAL_THRESHOLD = 60


def _signal_to_dict(item: CollectedItem, score: int, direction: str) -> dict:
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
        "glossaryTermId": item.extra.get("glossary_term_id") if item.extra else None,
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
) -> dict:
    filtered_for_economy = [
        s for s in scored_signals if s[1] >= ECONOMY_SIGNAL_THRESHOLD
    ]
    filtered_for_economy.sort(key=lambda t: t[1], reverse=True)

    hero = None
    if filtered_for_economy and filtered_for_economy[0][1] >= HERO_THRESHOLD:
        it, score, direction = filtered_for_economy[0]
        hero = _signal_to_dict(it, score, direction)
        filtered_for_economy = filtered_for_economy[1:]

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
                    _signal_to_dict(it, s, d) for it, s, d in filtered_for_economy
                ],
                "news": [_news_to_dict(n) for n in economy_news],
            },
        },
    }


def write_briefing(
    *, public_briefings_dir: Path, briefing: dict
) -> Path:
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
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_json_builder.py -v
git add src/news_briefing/delivery/json_builder.py tests/test_json_builder.py
git commit -m "feat(delivery): briefing JSON builder per ARCHITECTURE.md 6.4"
```

---

## Task 5: Backend — orchestrator v2 (glossary + JSON + new kakao format)

**Files:**
- Modify: `src/news_briefing/orchestrator.py`
- Modify: `tests/test_orchestrator.py` (or create test_orchestrator_v2.py)
- Modify: `src/news_briefing/config.py` (add public_briefings_dir)

- [ ] **Step 1: Extend Config**

Add to `Config` dataclass and `load_config`:

```python
# config.py 의 Config 에 추가:
public_briefings_dir: Path  # frontend/public/briefings

# load_config 안에서:
frontend_dir = root / "frontend"
public_briefings_dir = frontend_dir / "public" / "briefings"
public_briefings_dir.mkdir(parents=True, exist_ok=True)

# 반환 dict 에 추가
public_briefings_dir=public_briefings_dir,
```

- [ ] **Step 2: Update orchestrator to write JSON + new kakao format**

Changes to `run_morning`:
- After scoring, `ensure_glossary_entry` for each scored signal's detected term
- Attach term_id to `item.extra["glossary_term_id"]`  (CollectedItem is frozen, so rebuild via tuple in ScoredSignal or use a dict alongside)
- Actually: store glossary_term_id in a parallel dict keyed by ext_id
- Build briefing JSON and write
- Kakao text template: new format "데일리 브리핑 · N월 N일 / 공시 X건 · 뉴스 Y건" + URL `https://{VERCEL_URL}/?date=YYYY-MM-DD&tab=economy`

Because `CollectedItem` is frozen, use a dict `term_ids: dict[str, str]` (ext_id → term_id) and pass separately to `build_briefing_json`.

Let me keep the existing `CollectedItem` immutable approach but change the json_builder signature to accept term_ids dict.

Changes to `_signal_to_dict` — accept optional `term_ids: dict[str, str]`:

```python
def _signal_to_dict(
    item: CollectedItem, score: int, direction: str,
    term_ids: dict[str, str] | None = None,
) -> dict:
    ...
    "glossaryTermId": (term_ids or {}).get(item.ext_id),
    ...
```

And `build_briefing_json` takes `term_ids: dict[str, str] | None = None`.

- [ ] **Step 3: Test**

```python
# Add to test_orchestrator.py:
def test_run_morning_writes_briefing_json(tmp_path: Path, mocker) -> None:
    cfg = _cfg(tmp_path)
    # cfg.public_briefings_dir 이 tmp_path 아래라 가정 — 이미 tmp_path 기반
    mocker.patch("news_briefing.orchestrator.fetch_all_rss", return_value=[])
    mocker.patch("news_briefing.orchestrator.summarize", return_value="")
    mocker.patch("news_briefing.orchestrator._send_kakao")

    result = run_morning(cfg, dry_run=True, now=datetime(2026, 4, 22))
    briefing_path = cfg.public_briefings_dir / "2026-04-22.json"
    assert briefing_path.exists()
    data = json.loads(briefing_path.read_text(encoding="utf-8"))
    assert data["date"] == "2026-04-22"
    assert "economy" in data["tabs"]
```

Also update `_cfg` helper to include `public_briefings_dir=tmp_path / "frontend" / "public" / "briefings"`.

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py tests/test_config.py -v
git add src/news_briefing/orchestrator.py src/news_briefing/config.py src/news_briefing/delivery/json_builder.py tests/test_orchestrator.py tests/test_config.py
git commit -m "feat: orchestrator writes briefing JSON + glossary lookup + kakao link format"
```

---

## Task 6: Backend — kakao message link format

**Files:**
- Modify: `src/news_briefing/orchestrator.py` (`_send_kakao`)
- Modify: `src/news_briefing/config.py` (add `vercel_base_url`)

`DECISIONS.md` #10 + ROADMAP 11 — 카톡 본문 간소화 + Vercel URL 링크.

- [ ] **Step 1: Add `vercel_base_url` config**

In `.env.example`:
```
VERCEL_BASE_URL=https://your-project.vercel.app
```

In `config.py`:
```python
vercel_base_url=os.environ.get("VERCEL_BASE_URL", "https://news-briefing.vercel.app"),
```

- [ ] **Step 2: Update kakao message**

```python
# orchestrator._send_kakao 에서:
url = f"{cfg.vercel_base_url}/?date={now.strftime('%Y-%m-%d')}&tab=economy"
title = (
    f"데일리 브리핑 · {now.strftime('%m월 %d일')}\n"
    f"공시 {signal_count}건 · 뉴스 {news_count}건"
)
```

- [ ] **Step 3: commit**

```bash
git add -u
git commit -m "feat(delivery): kakao message links to Vercel URL with tab=economy"
```

---

## Task 7: Frontend — Next.js 15 + Tailwind 부트스트랩

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.mjs`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/.gitignore` (또는 root `.gitignore` 확인)
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/lib/types.ts`

- [ ] **Step 1: Initialize Next.js 15 project manually**

`frontend/package.json`:
```json
{
  "name": "news-briefing-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.5.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/postcss": "^4.0.0",
    "postcss": "^8.5.0"
  }
}
```

- [ ] **Step 2: next.config.mjs**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
};
export default nextConfig;
```

- [ ] **Step 3: tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules", "out"]
}
```

- [ ] **Step 4: tailwind.config.ts** (DESIGN.md 토큰)

```typescript
import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Pretendard Variable', 'Pretendard', 'system-ui', 'sans-serif'],
      },
      colors: {
        gray: {
          50: '#F9FAFB', 100: '#F2F4F6', 200: '#E5E8EB',
          300: '#D1D6DB', 400: '#B0B8C1', 500: '#8B95A1',
          600: '#6B7684', 700: '#4E5968', 800: '#333D4B',
          900: '#191F28',
        },
        signal: {
          critical: '#F04452',
          positive: '#3182F6',
          mixed: '#F79A34',
          neutral: '#8B95A1',
        },
      },
      borderRadius: {
        'card-sm': '16px', card: '18px',
        'card-lg': '20px', btn: '14px',
      },
      maxWidth: { 'briefing': '560px', 'picks': '720px' },
      fontSize: {
        'hero': ['26px', { lineHeight: '1.35', letterSpacing: '-0.03em', fontWeight: '700' }],
        'title-xl': ['24px', { lineHeight: '1.3', letterSpacing: '-0.03em', fontWeight: '700' }],
        'title-lg': ['20px', { lineHeight: '1.25', letterSpacing: '-0.03em', fontWeight: '700' }],
        'title-md': ['18px', { lineHeight: '1.3', letterSpacing: '-0.02em', fontWeight: '700' }],
      },
    },
  },
  plugins: [],
}
export default config
```

- [ ] **Step 5: postcss.config.mjs**

```javascript
const config = { plugins: { '@tailwindcss/postcss': {} } };
export default config;
```

- [ ] **Step 6: globals.css**

```css
@import "tailwindcss";

:root {
  --bg-page: #F9FAFB;
  --bg-card: #FFFFFF;
  --bg-inset: #F7F8FA;
  --text-primary: #191F28;
  --text-secondary: #4E5968;
  --text-tertiary: #6B7684;
  --border-subtle: #F2F4F6;
}

.dark {
  --bg-page: #191F28;
  --bg-card: #26262B;
  --bg-inset: #2C2C31;
  --text-primary: #F9FAFB;
  --text-secondary: #B0B8C1;
  --text-tertiary: #8B95A1;
  --border-subtle: #2F2F34;
}

html { font-family: 'Pretendard Variable', Pretendard, system-ui, sans-serif; }
body {
  background: var(--bg-page);
  color: var(--text-primary);
  font-feature-settings: 'tnum';
  font-variant-numeric: tabular-nums;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 7: app/layout.tsx** (시작 버전, TabBar 추가는 Task 9)

```tsx
import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '데일리 브리핑',
  description: '매일 아침 공시·뉴스 브리핑',
};

export default function RootLayout({
  children,
}: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
        <meta name="theme-color" content="#F9FAFB" media="(prefers-color-scheme: light)" />
        <meta name="theme-color" content="#191F28" media="(prefers-color-scheme: dark)" />
      </head>
      <body>
        <main className="mx-auto max-w-briefing px-4 py-9">{children}</main>
      </body>
    </html>
  )
}
```

- [ ] **Step 8: app/page.tsx** (최소 스모크)

```tsx
export default function HomePage() {
  return (
    <div>
      <h1 className="text-hero">데일리 브리핑</h1>
      <p className="text-[15px] text-gray-700 mt-4">오전 6:00에 업데이트했어요.</p>
    </div>
  )
}
```

- [ ] **Step 9: lib/types.ts** (JSON 스키마 타입 미러)

```typescript
export interface Briefing {
  date: string
  generatedAt: string
  version: number
  hero: SignalItem | null
  tabs: {
    current: CurrentTab
    economy: EconomyTab
    picks?: PicksTab  // Week 2b
  }
}

export interface CurrentTab {
  politics: NewsItem[]
  society: NewsItem[]
  international: NewsItem[]
  tech: NewsItem[]
}

export interface EconomyTab {
  indices: MarketIndex[]
  signals: SignalItem[]
  news: NewsItem[]
  themeBanner?: ThemeBanner
}

export interface PicksTab {
  domestic: SignalItem[]
  foreign: SignalItem[]
}

export interface SignalItem {
  id: string
  source: 'dart' | 'edgar'
  company: string
  companyCode: string | null
  headline: string
  summary: string
  score: number
  direction: 'positive' | 'negative' | 'mixed' | 'neutral'
  scope: 'domestic' | 'foreign'
  time: string
  url: string
  glossaryTermId: string | null
}

export interface NewsItem {
  id: string
  source: string
  title: string
  summary: string
  url: string
  thumbnail: string | null
  time: string
  scope: 'domestic' | 'foreign'
  glossaryTermId: string | null
  curationScore: number
}

export interface MarketIndex {
  name: string
  value: string
  change: string
  direction: 'up' | 'down' | 'flat'
}

export interface ThemeBanner {
  trendingThemes: string[]
  reportUrl: string
}
```

- [ ] **Step 10: Install + dev server check**

```bash
cd frontend && npm install
cd frontend && npm run build
cd frontend && npm run dev &
```

웹 `http://localhost:3000` 접속 → "데일리 브리핑" 헤드라인 보이면 OK. (dev 서버는 Ctrl+C)

- [ ] **Step 11: Update root .gitignore**

```gitignore
# 추가:
frontend/.next/
frontend/out/
frontend/node_modules/
```

(이미 gitignore 에 있음 확인만)

- [ ] **Step 12: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Next.js 15 + Tailwind 4 + design tokens bootstrap"
```

---

## Task 8: Frontend — fetchBriefing + theme + i18n 기반 유틸

**Files:**
- Create: `frontend/src/lib/fetchBriefing.ts`
- Create: `frontend/src/lib/theme.ts`
- Create: `frontend/src/lib/i18n.ts`
- Create: `frontend/src/lib/i18n/ko.ts`
- Create: `frontend/src/lib/i18n/en.ts`
- Create: `frontend/src/lib/tabs.ts`

- [ ] **Step 1: fetchBriefing.ts**

```typescript
import type { Briefing } from '@/lib/types'

export async function fetchBriefing(date?: string): Promise<Briefing> {
  const path = date ? `/briefings/${date}.json` : `/briefings/${todayKey()}.json`
  const resp = await fetch(path, { cache: 'no-cache' })
  if (!resp.ok) throw new Error(`briefing fetch failed: ${resp.status}`)
  return resp.json()
}

export async function fetchBriefingIndex(): Promise<{ dates: string[] }> {
  const resp = await fetch('/briefings/index.json', { cache: 'no-cache' })
  if (!resp.ok) return { dates: [] }
  return resp.json()
}

function todayKey(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
```

- [ ] **Step 2: theme.ts**

```typescript
export type Theme = 'light' | 'dark'
const KEY = 'news-briefing:theme'

export function getStoredTheme(): Theme | null {
  if (typeof window === 'undefined') return null
  const v = localStorage.getItem(KEY)
  return v === 'light' || v === 'dark' ? v : null
}

export function storeTheme(t: Theme) {
  localStorage.setItem(KEY, t)
}

export function systemPrefersDark(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function applyTheme(t: Theme) {
  const root = document.documentElement
  if (t === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
}
```

- [ ] **Step 3: i18n/ko.ts, en.ts**

`ko.ts`:
```typescript
export const ko = {
  'tab.current': '시사',
  'tab.economy': '경제',
  'tab.picks': '종목',
  'scope.all': '전체',
  'scope.domestic': '국내',
  'scope.foreign': '해외',
  'hero.today': '지금 가장 중요해요',
  'signal.positive': '긍정 시그널',
  'signal.negative': '주의할 공시',
  'signal.mixed': '복합 시그널',
  'signal.neutral': '중립',
  'cta.more': '자세히 →',
  'cta.seeAll': (n: number) => `전체 ${n}건 모두 보기 →`,
  'cta.open': '열기',
  'empty.economy': '오늘은 조용한 장이에요. 주목할 공시가 없어요.',
  'empty.current': '아직 오늘 새 소식이 많지 않아요. 곧 업데이트될 거예요.',
  'loading': '불러오는 중이에요.',
  'error.fetch': '잠깐, 불러오지 못했어요.',
  'install.title': '홈 화면에 추가해보세요',
  'install.cta': '설치',
  'install.subtitle': '앱처럼 바로 열려요',
  'glossary.heading': (label: string) => `${label}가 뭐예요?`,
  'glossary.acknowledge': '알겠어요',
} as const
export type Dict = typeof ko
```

`en.ts`:
```typescript
import type { Dict } from './ko'
export const en: Dict = {
  'tab.current': 'News',
  'tab.economy': 'Economy',
  'tab.picks': 'Picks',
  'scope.all': 'All',
  'scope.domestic': 'Korea',
  'scope.foreign': 'Global',
  'hero.today': 'Needs your attention',
  'signal.positive': 'Positive',
  'signal.negative': 'Alert',
  'signal.mixed': 'Mixed',
  'signal.neutral': 'Neutral',
  'cta.more': 'More →',
  'cta.seeAll': (n: number) => `See all ${n} →`,
  'cta.open': 'Open',
  'empty.economy': 'Quiet market today.',
  'empty.current': "We don't have much new today. Check back soon.",
  'loading': 'Loading...',
  'error.fetch': 'Hmm, couldn\'t load that.',
  'install.title': 'Add to Home Screen',
  'install.cta': 'Install',
  'install.subtitle': 'Opens like an app',
  'glossary.heading': (label: string) => `What is ${label}?`,
  'glossary.acknowledge': 'Got it',
}
```

- [ ] **Step 4: i18n.ts entry**

```typescript
import { ko, type Dict } from './i18n/ko'
import { en } from './i18n/en'

export type Lang = 'ko' | 'en'
const KEY = 'news-briefing:lang'

const DICT: Record<Lang, Dict> = { ko, en }

export function getStoredLang(): Lang {
  if (typeof window === 'undefined') return 'ko'
  const v = localStorage.getItem(KEY)
  if (v === 'ko' || v === 'en') return v
  const browser = navigator.language?.slice(0, 2)
  return browser === 'en' ? 'en' : 'ko'
}

export function storeLang(lang: Lang) {
  localStorage.setItem(KEY, lang)
}

export function t(lang: Lang): Dict {
  return DICT[lang]
}
```

- [ ] **Step 5: tabs.ts**

```typescript
export type Tab = 'current' | 'economy' | 'picks'
export type Scope = 'all' | 'domestic' | 'foreign'

const TABS_SET: ReadonlySet<string> = new Set(['current', 'economy', 'picks'])
const SCOPES_SET: ReadonlySet<string> = new Set(['all', 'domestic', 'foreign'])

export function parseTabFromSearch(search: string): Tab {
  const p = new URLSearchParams(search)
  const v = p.get('tab')
  return TABS_SET.has(v ?? '') ? (v as Tab) : 'current'
}

export function parseScopeFromSearch(search: string): Scope {
  const p = new URLSearchParams(search)
  const v = p.get('scope')
  return SCOPES_SET.has(v ?? '') ? (v as Scope) : 'all'
}

export function tabHref(tab: Tab, scope: Scope = 'all', date?: string): string {
  const p = new URLSearchParams()
  if (date) p.set('date', date)
  p.set('tab', tab)
  if (scope !== 'all') p.set('scope', scope)
  return `/?${p.toString()}`
}
```

- [ ] **Step 6: Build check + commit**

```bash
cd frontend && npm run build
git add frontend/src/lib/
git commit -m "feat(frontend): fetchBriefing + theme + i18n + tabs utils"
```

---

## Task 9: Frontend — TabBar + ScopeFilter + ThemeToggle + LangToggle

**Files:**
- Create: `frontend/src/components/TabBar.tsx`
- Create: `frontend/src/components/ScopeFilter.tsx`
- Create: `frontend/src/components/ThemeToggle.tsx`
- Create: `frontend/src/components/LangToggle.tsx`

모든 컴포넌트는 `'use client'` (상태·URL 접근 필요).

- [ ] **Step 1: TabBar.tsx**

```tsx
'use client'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { parseTabFromSearch, tabHref, type Tab } from '@/lib/tabs'
import { t, type Lang } from '@/lib/i18n'

export function TabBar({ lang }: { lang: Lang }) {
  const sp = useSearchParams()
  const currentTab = parseTabFromSearch(sp.toString())
  const dict = t(lang)
  // Week 2a 는 2탭. Week 2b 에 'picks' 추가.
  const tabs: { key: Tab; label: string }[] = [
    { key: 'current', label: dict['tab.current'] },
    { key: 'economy', label: dict['tab.economy'] },
  ]

  return (
    <nav className="flex gap-2 px-5 pb-4.5" role="tablist">
      {tabs.map(({ key, label }) => {
        const active = currentTab === key
        return (
          <Link
            key={key}
            href={tabHref(key)}
            role="tab"
            aria-selected={active}
            className={`min-w-[100px] rounded-full px-6 py-3 text-[15px] tracking-tight transition-colors ${
              active
                ? 'bg-gray-50 text-gray-900 font-bold dark:bg-gray-800'
                : 'bg-transparent text-gray-500 font-semibold'
            }`}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
```

- [ ] **Step 2: ScopeFilter.tsx**

```tsx
'use client'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { parseTabFromSearch, parseScopeFromSearch, tabHref, type Scope } from '@/lib/tabs'
import { t, type Lang } from '@/lib/i18n'

export function ScopeFilter({ lang }: { lang: Lang }) {
  const sp = useSearchParams()
  const tab = parseTabFromSearch(sp.toString())
  const scope = parseScopeFromSearch(sp.toString())
  const dict = t(lang)
  const options: Scope[] = ['all', 'domestic', 'foreign']

  return (
    <div className="flex gap-5 px-5 py-3.5 border-b border-gray-100 dark:border-gray-800">
      {options.map((s) => {
        const active = scope === s
        return (
          <Link
            key={s}
            href={tabHref(tab, s)}
            className={`relative text-sm tracking-tight pb-1.5 ${
              active
                ? 'text-gray-900 dark:text-gray-50 font-bold'
                : 'text-gray-500 font-medium'
            }`}
          >
            {s === 'all'
              ? dict['scope.all']
              : s === 'domestic'
              ? dict['scope.domestic']
              : dict['scope.foreign']}
            {active && (
              <span className="absolute -bottom-[14.5px] left-0 right-0 h-0.5 bg-gray-900 dark:bg-gray-50 rounded-sm" />
            )}
          </Link>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: ThemeToggle.tsx** + **LangToggle.tsx**

```tsx
// ThemeToggle.tsx
'use client'
import { useEffect, useState } from 'react'
import { applyTheme, getStoredTheme, storeTheme, systemPrefersDark, type Theme } from '@/lib/theme'

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>('light')

  useEffect(() => {
    const stored = getStoredTheme()
    const initial: Theme = stored ?? (systemPrefersDark() ? 'dark' : 'light')
    setTheme(initial)
    applyTheme(initial)
  }, [])

  function toggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    storeTheme(next)
    applyTheme(next)
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="p-2 rounded-btn text-gray-700 dark:text-gray-200"
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
```

```tsx
// LangToggle.tsx
'use client'
import { useEffect, useState } from 'react'
import { getStoredLang, storeLang, type Lang } from '@/lib/i18n'

export function LangToggle({ onChange }: { onChange?: (l: Lang) => void }) {
  const [lang, setLang] = useState<Lang>('ko')
  useEffect(() => setLang(getStoredLang()), [])
  function toggle() {
    const next: Lang = lang === 'ko' ? 'en' : 'ko'
    setLang(next)
    storeLang(next)
    onChange?.(next)
    location.reload()
  }
  return (
    <button onClick={toggle} className="p-2 text-xs font-bold text-gray-700 dark:text-gray-200">
      {lang === 'ko' ? 'KO / EN' : 'EN / KO'}
    </button>
  )
}
```

- [ ] **Step 4: Update layout.tsx to use TabBar**

```tsx
// layout.tsx (수정)
import { TabBar } from '@/components/TabBar'
import { ScopeFilter } from '@/components/ScopeFilter'
import { ThemeToggle } from '@/components/ThemeToggle'
import { LangToggle } from '@/components/LangToggle'
import { Suspense } from 'react'

// ...
<body>
  <header className="flex items-center justify-between px-5 pt-9 pb-2">
    <h1 className="text-hero">데일리 브리핑</h1>
    <div className="flex items-center gap-1">
      <Suspense fallback={null}><LangToggle /></Suspense>
      <ThemeToggle />
    </div>
  </header>
  <Suspense fallback={null}><TabBar lang="ko" /></Suspense>
  <Suspense fallback={null}><ScopeFilter lang="ko" /></Suspense>
  <main className="mx-auto max-w-briefing">{children}</main>
</body>
```

- [ ] **Step 5: Build check + commit**

```bash
cd frontend && npm run build
git add frontend/src/components/ frontend/src/app/layout.tsx
git commit -m "feat(frontend): TabBar + ScopeFilter + Theme/Lang toggles"
```

---

## Task 10: Frontend — SignalCard + HeroCard + CurrentNewsCard + MarketIndices

**Files:**
- Create: `frontend/src/components/SignalCard.tsx`
- Create: `frontend/src/components/HeroCard.tsx`
- Create: `frontend/src/components/CurrentNewsCard.tsx`
- Create: `frontend/src/components/MarketIndices.tsx`

`DESIGN.md` 5.1–5.2, 5.4, 5.8, 5.10 기준.

- [ ] **Step 1: SignalCard.tsx**

```tsx
import type { SignalItem } from '@/lib/types'
import { GlossaryPopover } from './GlossaryPopover'

const toneMap = {
  positive: { color: '#3182F6', label: '긍정 시그널' },
  negative: { color: '#F04452', label: '주의할 공시' },
  mixed: { color: '#F79A34', label: '복합 시그널' },
  neutral: { color: '#8B95A1', label: '중립' },
} as const

export function SignalCard({ signal }: { signal: SignalItem }) {
  const tone = toneMap[signal.direction]
  const time = new Date(signal.time).toLocaleTimeString('ko-KR', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })

  return (
    <article className="bg-[var(--bg-card)] rounded-card px-[22px] pb-[18px] pt-[22px] mx-4 mb-2.5">
      <div className="flex items-center gap-[7px] mb-4">
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: tone.color }}
          aria-label={tone.label}
        />
        <span
          className="text-[13px] font-bold tracking-tight"
          style={{ color: tone.color }}
        >
          {tone.label}
        </span>
        <span className="ml-auto text-xs font-medium text-[var(--text-tertiary)]">
          {time}
        </span>
      </div>
      <h3 className="text-title-lg text-[var(--text-primary)] mb-2">
        {signal.company || '—'}
      </h3>
      <p className="text-[15px] font-semibold text-[var(--text-secondary)] mb-2.5 tracking-tight">
        {signal.headline}
      </p>
      {signal.summary && (
        <p className="text-sm text-[var(--text-secondary)] leading-[1.7]">
          {signal.summary}
        </p>
      )}
      {signal.glossaryTermId && (
        <GlossaryPopover termId={signal.glossaryTermId} />
      )}
      <div className="flex items-center mt-5 pt-3.5 border-t border-[var(--border-subtle)]">
        <a
          href={signal.url}
          target="_blank"
          rel="noopener"
          className="ml-auto text-[13px] font-bold text-[var(--text-primary)]"
        >
          자세히 →
        </a>
      </div>
    </article>
  )
}
```

- [ ] **Step 2: HeroCard.tsx**

```tsx
import type { SignalItem } from '@/lib/types'
import { GlossaryPopover } from './GlossaryPopover'

export function HeroCard({ signal }: { signal: SignalItem }) {
  const color = signal.direction === 'negative' ? '#F04452' : '#3182F6'
  return (
    <article className="bg-[var(--bg-card)] rounded-card-lg p-7 mx-4 mb-2.5">
      <div className="flex items-center gap-[7px] mb-5">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
        <span className="text-[13px] font-bold" style={{ color }}>
          지금 가장 중요해요
        </span>
      </div>
      <h2 className="text-title-xl text-[var(--text-primary)] mb-2">{signal.company || '—'}</h2>
      <p className="text-[17px] font-medium text-[var(--text-secondary)] mb-5 tracking-tight">
        {signal.headline}
      </p>
      {signal.summary && (
        <p className="text-[15px] text-[var(--text-secondary)] leading-[1.7] mb-6">
          {signal.summary}
        </p>
      )}
      {signal.glossaryTermId && (
        <GlossaryPopover termId={signal.glossaryTermId} defaultOpen />
      )}
      <div className="mt-6">
        <a
          href={signal.url}
          target="_blank"
          rel="noopener"
          className="block w-full text-center bg-gray-900 text-white rounded-btn py-[17px] text-[15px] font-bold"
        >
          공시 원문 보기
        </a>
      </div>
    </article>
  )
}
```

- [ ] **Step 3: CurrentNewsCard.tsx**

```tsx
import type { NewsItem } from '@/lib/types'

export function CurrentNewsCard({ news }: { news: NewsItem }) {
  const time = new Date(news.time).toLocaleTimeString('ko-KR', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
  return (
    <article className="bg-[var(--bg-card)] rounded-card px-[22px] pb-[18px] pt-[22px] mx-4 mb-2.5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-[var(--text-tertiary)] font-medium">{news.source}</span>
        <span className="ml-auto text-xs text-[var(--text-tertiary)] font-medium">{time}</span>
      </div>
      <h3 className="text-[17px] font-bold text-[var(--text-primary)] tracking-tight leading-snug mb-2">
        {news.title}
      </h3>
      {news.summary && (
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{news.summary}</p>
      )}
      <div className="flex items-center mt-5 pt-3.5 border-t border-[var(--border-subtle)]">
        <a
          href={news.url}
          target="_blank"
          rel="noopener"
          className="ml-auto text-[13px] font-bold text-[var(--text-primary)]"
        >
          자세히 →
        </a>
      </div>
    </article>
  )
}
```

- [ ] **Step 4: MarketIndices.tsx**

```tsx
import type { MarketIndex } from '@/lib/types'

export function MarketIndices({ indices }: { indices: MarketIndex[] }) {
  if (indices.length === 0) return null
  return (
    <section className="mx-4 mb-2.5 bg-[var(--bg-card)] rounded-card p-6">
      <div className="text-xs font-bold text-[var(--text-tertiary)] uppercase tracking-wide mb-4">
        오늘 시장
      </div>
      <div className="grid grid-cols-3 gap-4">
        {indices.map((m) => (
          <div key={m.name}>
            <div className="text-xs text-[var(--text-tertiary)] font-medium mb-1.5">{m.name}</div>
            <div className="text-[22px] font-bold text-[var(--text-primary)] tabular-nums">
              {m.value}
            </div>
            <div
              className={`text-[13px] font-bold ${
                m.direction === 'up'
                  ? 'text-[#F04452]'
                  : m.direction === 'down'
                  ? 'text-[#3182F6]'
                  : 'text-gray-500'
              }`}
            >
              {m.change}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 5: Build check + commit**

```bash
cd frontend && npm run build
git add frontend/src/components/
git commit -m "feat(frontend): SignalCard + HeroCard + CurrentNewsCard + MarketIndices"
```

---

## Task 11: Frontend — GlossaryPopover

**Files:**
- Create: `frontend/src/components/GlossaryPopover.tsx`
- Create: `frontend/src/lib/glossaryStore.ts`

용어 해설은 현재 JSON 에 포함되지 않으므로 **별도 endpoint** 가 필요합니다. Week 2a 에서는 **백엔드 JSON builder 가 glossary 맵을 briefing JSON 에 embed** 하는 방식으로 단순화 — `Briefing.glossary?: Record<string, GlossaryEntry>`.

- [ ] **Step 1: Extend backend JSON builder to include glossary**

`build_briefing_json` 에 `glossary: dict[str, GlossaryEntry]` 추가. 호출부(`orchestrator.run_morning`)에서 각 signal 의 term_id 로 `ensure_glossary_entry` 호출 후 dict 구축.

```python
# json_builder 에 필드 추가:
return {
    ...
    "glossary": glossary or {},
}
```

`types.ts` 에 추가:
```typescript
export interface Briefing {
  ...
  glossary?: Record<string, {
    shortLabel: string
    explanation: string
    direction: 'positive' | 'negative' | 'mixed' | 'neutral' | null
  }>
}
```

- [ ] **Step 2: GlossaryPopover.tsx**

```tsx
'use client'
import { useEffect, useState } from 'react'
import { getGlossary } from '@/lib/glossaryStore'

export function GlossaryPopover({
  termId,
  defaultOpen = false,
}: {
  termId: string
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  const [entry, setEntry] = useState<{
    shortLabel: string
    explanation: string
  } | null>(null)

  useEffect(() => {
    setEntry(getGlossary(termId))
  }, [termId])

  if (!entry) return null

  return (
    <div className="mt-4">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="w-full text-left bg-[var(--bg-inset)] rounded-btn p-4 text-[13px] font-medium text-[var(--text-tertiary)]"
        >
          💡 {entry.shortLabel}가 뭐예요? <span className="float-right">탭</span>
        </button>
      ) : (
        <div className="bg-[var(--bg-inset)] rounded-btn p-4.5">
          <div className="text-[13px] font-bold text-[var(--text-tertiary)] mb-2">
            {entry.shortLabel}가 뭐예요?
          </div>
          <div className="text-sm text-[var(--text-secondary)] leading-[1.65]">
            {entry.explanation}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: glossaryStore.ts** (page.tsx 에서 fetchBriefing 후 세팅)

```typescript
let _cache: Record<string, { shortLabel: string; explanation: string }> = {}

export function setGlossary(g: Record<string, { shortLabel: string; explanation: string }>) {
  _cache = g
}

export function getGlossary(termId: string) {
  return _cache[termId] ?? null
}
```

- [ ] **Step 4: page.tsx 에서 briefing 로드 + glossary 세팅**

`app/page.tsx` 를 client component 로 전환 (상태 필요):

```tsx
'use client'
import { useEffect, useState } from 'react'
import { fetchBriefing } from '@/lib/fetchBriefing'
import { setGlossary } from '@/lib/glossaryStore'
import { parseTabFromSearch, parseScopeFromSearch } from '@/lib/tabs'
import { HeroCard } from '@/components/HeroCard'
import { SignalCard } from '@/components/SignalCard'
import { CurrentNewsCard } from '@/components/CurrentNewsCard'
import { MarketIndices } from '@/components/MarketIndices'
import type { Briefing } from '@/lib/types'
import { useSearchParams } from 'next/navigation'

export default function HomePage() {
  const sp = useSearchParams()
  const tab = parseTabFromSearch(sp.toString())
  const scope = parseScopeFromSearch(sp.toString())
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchBriefing()
      .then((b) => {
        setBriefing(b)
        if (b.glossary) setGlossary(b.glossary as any)
      })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="px-5 py-10 text-center">잠깐, 불러오지 못했어요.</p>
  if (!briefing) return <p className="px-5 py-10 text-center">불러오는 중이에요.</p>

  if (tab === 'economy') {
    const signals = briefing.tabs.economy.signals.filter(
      (s) => scope === 'all' || s.scope === scope
    )
    return (
      <div className="pb-20">
        {briefing.hero && <HeroCard signal={briefing.hero} />}
        <MarketIndices indices={briefing.tabs.economy.indices} />
        {signals.length === 0 ? (
          <p className="px-5 py-20 text-center text-[var(--text-secondary)]">
            오늘은 조용한 장이에요.
          </p>
        ) : (
          signals.map((s) => <SignalCard key={s.id} signal={s} />)
        )}
      </div>
    )
  }

  // current tab
  const allNews = [
    ...briefing.tabs.current.politics,
    ...briefing.tabs.current.society,
    ...briefing.tabs.current.international,
    ...briefing.tabs.current.tech,
  ].filter((n) => scope === 'all' || n.scope === (scope === 'domestic' ? 'domestic' : 'foreign'))

  return (
    <div className="pb-20">
      {allNews.length === 0 ? (
        <p className="px-5 py-20 text-center text-[var(--text-secondary)]">
          아직 오늘 새 소식이 많지 않아요.
        </p>
      ) : (
        allNews.map((n) => <CurrentNewsCard key={n.id} news={n} />)
      )}
    </div>
  )
}
```

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run build
git add frontend/src/components/GlossaryPopover.tsx frontend/src/lib/glossaryStore.ts frontend/src/app/page.tsx frontend/src/lib/types.ts src/news_briefing/delivery/json_builder.py
git commit -m "feat(frontend): GlossaryPopover with embedded glossary map + page wiring"
```

---

## Task 12: Backend — orchestrator writes glossary map into JSON

**Files:**
- Modify: `src/news_briefing/orchestrator.py`
- Modify: `src/news_briefing/delivery/json_builder.py`

Already mentioned in Task 11. Consolidate here:

- [ ] **Step 1: In orchestrator.run_morning**

After scoring, loop:
```python
from news_briefing.analysis.glossary import detect_term, ensure_glossary_entry

glossary_map: dict[str, dict] = {}
for item, score, direction in scored:
    term_id = detect_term(item.title)
    if term_id:
        entry = ensure_glossary_entry(conn, term_id, lang="ko")
        if entry:
            glossary_map[term_id] = {
                "shortLabel": entry.short_label,
                "explanation": entry.explanation,
                "direction": entry.signal_direction,
            }
        # attach term_id via parallel dict since CollectedItem is frozen
        term_ids_by_id[item.ext_id] = term_id

briefing = build_briefing_json(
    date=now, scored_signals=scored, economy_news=fresh_news,
    glossary=glossary_map, term_ids=term_ids_by_id,
)
write_briefing(public_briefings_dir=cfg.public_briefings_dir, briefing=briefing)
```

- [ ] **Step 2: Test**

```python
def test_morning_writes_glossary_map(tmp_path: Path, mocker) -> None:
    cfg = _cfg(tmp_path)
    sample = CollectedItem(
        source="dart", ext_id="abc", kind="disclosure",
        title="자기주식취득결정", url="x",
        published_at=datetime(2026, 4, 22),
        company="삼성전자", company_code="005930",
    )
    mocker.patch("news_briefing.collectors.dart.fetch_dart_list", return_value=[sample])
    mocker.patch("news_briefing.orchestrator.fetch_all_rss", return_value=[])
    mocker.patch("news_briefing.orchestrator.summarize", return_value="")
    mocker.patch("news_briefing.orchestrator._send_kakao")

    run_morning(cfg, dry_run=True, now=datetime(2026, 4, 22))
    path = cfg.public_briefings_dir / "2026-04-22.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "self_stock_buy" in data["glossary"]
    assert data["glossary"]["self_stock_buy"]["shortLabel"]
```

- [ ] **Step 3: Commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v
git add src/news_briefing/orchestrator.py src/news_briefing/delivery/json_builder.py tests/test_orchestrator.py
git commit -m "feat: orchestrator computes glossary map per briefing"
```

---

## Task 13: Frontend — PWA manifest + icons + service worker + InstallPrompt

**Files:**
- Create: `scripts/generate_icons.py`
- Create: `frontend/public/icons/icon-192.png` (generated)
- Create: `frontend/public/icons/icon-512.png` (generated)
- Create: `frontend/public/icons/apple-touch-icon.png` (generated)
- Create: `frontend/public/manifest.json`
- Create: `frontend/public/sw.js`
- Create: `frontend/src/components/InstallPrompt.tsx`
- Modify: `frontend/src/app/layout.tsx` (register SW + manifest link)
- Modify: `pyproject.toml` (add Pillow to dev deps)

- [ ] **Step 1: Pillow 추가 + 아이콘 생성 스크립트**

```bash
uv pip install --python .venv/Scripts/python.exe pillow
```

Append to `pyproject.toml` dev deps:
```toml
dev = [..., "pillow>=11.0.0"]
```

`scripts/generate_icons.py`:
```python
"""PWA 아이콘 placeholder 생성 (`#191F28` 배경 + 'DB' 흰 글자)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "icons"
OUT.mkdir(parents=True, exist_ok=True)


def make(size: int, name: str) -> None:
    img = Image.new("RGBA", (size, size), (25, 31, 40, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", int(size * 0.45))
    except Exception:
        font = ImageFont.load_default()
    text = "DB"
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2, (size - h) / 2 - bbox[1]), text, fill=(249, 250, 251), font=font)
    img.save(OUT / name)
    print(f"wrote {OUT / name}")


if __name__ == "__main__":
    make(192, "icon-192.png")
    make(512, "icon-512.png")
    make(180, "apple-touch-icon.png")
```

Run:
```bash
.venv/Scripts/python.exe scripts/generate_icons.py
```

- [ ] **Step 2: manifest.json**

```json
{
  "name": "데일리 브리핑",
  "short_name": "브리핑",
  "description": "매일 아침 공시·뉴스 브리핑",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#F9FAFB",
  "theme_color": "#F9FAFB",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
```

- [ ] **Step 3: sw.js**

```javascript
// frontend/public/sw.js
const CACHE_VERSION = 'v1'
const SHELL = `shell-${CACHE_VERSION}`
const DATA = `data-${CACHE_VERSION}`
const SHELL_URLS = ['/', '/manifest.json']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_URLS)))
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => !k.endsWith(CACHE_VERSION)).map((k) => caches.delete(k))
      )
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)

  // /briefings/*.json: network-first with cache fallback
  if (url.pathname.startsWith('/briefings/')) {
    e.respondWith(
      fetch(e.request)
        .then((resp) => {
          const copy = resp.clone()
          caches.open(DATA).then((c) => c.put(e.request, copy))
          return resp
        })
        .catch(() => caches.match(e.request))
    )
    return
  }

  // app shell: cache-first
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request))
  )
})
```

- [ ] **Step 4: InstallPrompt.tsx**

```tsx
'use client'
import { useEffect, useState } from 'react'

const DISMISSED_KEY = 'news-briefing:install-dismissed-at'
const COOLDOWN_DAYS = 7

export function InstallPrompt() {
  const [deferred, setDeferred] = useState<any>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const h = (e: any) => {
      e.preventDefault()
      const dismissedAt = Number(localStorage.getItem(DISMISSED_KEY) || 0)
      const cooldown = dismissedAt + COOLDOWN_DAYS * 24 * 3600 * 1000
      if (Date.now() < cooldown) return
      setDeferred(e)
      setVisible(true)
    }
    window.addEventListener('beforeinstallprompt', h)
    return () => window.removeEventListener('beforeinstallprompt', h)
  }, [])

  if (!visible) return null

  async function install() {
    if (!deferred) return
    deferred.prompt()
    await deferred.userChoice
    setVisible(false)
  }

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, String(Date.now()))
    setVisible(false)
  }

  return (
    <div className="fixed bottom-4 inset-x-4 bg-gray-800 text-white rounded-card p-5 flex items-center gap-3 z-50">
      <div className="flex-1">
        <div className="text-[15px] font-bold">홈 화면에 추가해보세요</div>
        <div className="text-[13px] text-gray-300">앱처럼 바로 열려요</div>
      </div>
      <button onClick={dismiss} className="text-[13px] text-gray-400">닫기</button>
      <button onClick={install} className="bg-white text-gray-900 rounded-btn px-4 py-2 text-[13px] font-bold">
        설치
      </button>
    </div>
  )
}
```

- [ ] **Step 5: layout.tsx 에 SW 등록 + manifest link + InstallPrompt**

```tsx
// layout.tsx 의 head:
<link rel="manifest" href="/manifest.json" />
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />

// body 끝:
<Script id="sw-register" strategy="afterInteractive">
  {`if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'));
  }`}
</Script>
<InstallPrompt />
```

(import `Script from 'next/script'`, `InstallPrompt` from `@/components/InstallPrompt`)

- [ ] **Step 6: Build + commit**

```bash
cd frontend && npm run build
# 빌드 시 out/ 디렉토리에 manifest, icons, sw.js 포함됐는지 확인
ls frontend/out/manifest.json frontend/out/icons frontend/out/sw.js

git add scripts/generate_icons.py pyproject.toml frontend/public/ frontend/src/components/InstallPrompt.tsx frontend/src/app/layout.tsx
git commit -m "feat(frontend): PWA manifest + icons + service worker + install prompt"
```

---

## Task 14: Frontend — Build + export sanity, write README

**Files:**
- Create: `frontend/README.md`

- [ ] **Step 1: Build + export local verify**

```bash
cd frontend && npm run build
ls frontend/out/  # 정적 HTML 생성 확인
```

- [ ] **Step 2: frontend/README.md**

```markdown
# news-briefing frontend

Next.js 15 static export PWA. Vercel 에 배포.

## Dev

```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

## Build

```bash
npm run build   # → frontend/out/
```

## Data source

`frontend/public/briefings/YYYY-MM-DD.json` 은 백엔드 `python -m news_briefing morning`
실행 시 자동 생성. `frontend/public/briefings/index.json` 에 날짜 목록.

## Deployment

Vercel 에 GitHub 저장소 연결. Build command 는 `cd frontend && npm install && npm run build`,
output directory 는 `frontend/out`. `vercel.json` 으로 설정 예정.
```

- [ ] **Step 3: vercel.json at repo root**

```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/out",
  "framework": null
}
```

- [ ] **Step 4: commit**

```bash
git add frontend/README.md vercel.json
git commit -m "chore(frontend): build docs + Vercel config"
```

---

## Task 15: E2E dry-run verification

- [ ] **Step 1: backend dry-run**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m news_briefing morning --dry-run
```

Expected:
- `data/digests/YYYY-MM-DD.txt` 생성
- `frontend/public/briefings/YYYY-MM-DD.json` 생성
- `frontend/public/briefings/index.json` 업데이트

- [ ] **Step 2: frontend build + export**

```bash
cd frontend && npm run build
```

Expected: out/ 디렉토리에 index.html, briefings/, icons/, manifest.json, sw.js

- [ ] **Step 3: local HTTP serve + browser check**

```bash
cd frontend/out && python -m http.server 8000
```

브라우저 `http://localhost:8000/`:
- 헤더 "데일리 브리핑" 보임
- TabBar 시사/경제 전환 동작
- 경제 탭에서 SignalCard 렌더, 점수 dot 색상 올바름
- 용어 해설 chip 탭 → 펼침
- 다크 모드 토글 동작
- KO/EN 토글 동작
- 오프라인 전환 → 리프레시 → 캐시된 페이지 보임

- [ ] **Step 4: pytest 전체**

```bash
.venv/Scripts/python.exe -m pytest 2>&1 | tail -5
```

Expected: all tests pass (Week 1 62 + Week 2a 추가분).

- [ ] **Step 5: ruff**

```bash
.venv/Scripts/python.exe -m ruff check src tests
```

- [ ] **Step 6: Commit pytest / ruff adjustments (if any)**

```bash
git status
# 변경 없으면 스킵
```

---

## Week 2a Definition of Done

- [x] `frontend/` 에서 `npm run dev` 실행 시 로컬 앱 로드됨 — **Task 7**
- [ ] Vercel 배포된 URL 접속 시 앱 로드 — **사용자 GitHub push + Vercel 연결 액션 후**
- [x] **홈 화면 설치 가능** — **Task 13**, 실제 설치 검증은 배포 후
- [x] **오프라인 상태에서 마지막 브리핑 열람 가능** — **Task 13 sw.js** (local verify)
- [x] 다크/라이트 모드 자동 감지 + 수동 토글 — **Task 9 ThemeToggle**
- [x] KO ↔ EN 토글 — **Task 9 LangToggle + Task 8 i18n**
- [x] **2탭 (시사·경제) 전환 동작**, URL 쿼리 동기화 — **Task 9 TabBar + ScopeFilter**
- [x] 카톡 메시지에 용어 해설 연결 (앱에서 챕 → 해설 노출) — **Task 11 GlossaryPopover**
- [x] 카톡 "열기" 클릭 시 경제 탭으로 직접 진입 — **Task 6 `?tab=economy`**
- [x] 시그널 점수가 금액·비율에 따라 차별화 — **Task 1 scoring v2**
- [x] 토스 디자인 원칙 5가지 준수 — **Task 7–11** 카드 디자인 (border/shadow 없음, dot+레이블, one action, 여백)

---

## Self-Review

**Spec coverage check (ROADMAP Week 2a 작업 항목 11개):**

1. Next.js + Tailwind 초기화 → Task 7 ✅
2. PWA manifest + sw → Task 13 ✅
3. Vercel 배포 파이프라인 → Task 14 (구성 파일), 실제 배포는 사용자
4. JSON export → Task 4 + Task 12 ✅
5. 탭 네비 UI → Task 9 ✅
6. 공통 컴포넌트 → Tasks 10, 11 ✅
7. 다크 모드 → Task 7 (CSS) + Task 9 (toggle) ✅
8. 용어 주석 엔진 → Tasks 2, 3 + Task 11 ✅
9. 시그널 v2 → Task 1 ✅
10. i18n → Task 8 + Task 9 ✅
11. 카톡 링크 방식 → Task 6 ✅

**Placeholder scan:** 없음 확인.

**Type consistency:** `Briefing.tabs` 가 backend `build_briefing_json` 과 frontend `lib/types.ts` 에서 일치. `glossary` 는 Task 11 에서 양쪽 동시 추가.

**Scope creep risk:** Vercel 실제 배포, 실제 디바이스 설치 검증 등은 사용자 액션이 필요. DoD 에서 분리 표시.
