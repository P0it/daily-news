# Week 2b: 종목 탭 (Today's Pick) + SEC EDGAR + 차트·딥링크 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Week 2a PWA 기반 위에 **종목 탭 (Today's Pick, `DECISIONS.md` #12)** 를 추가한다. 국내(DART)/해외(SEC EDGAR) 시그널 상위 종목을 데스크탑 2×컬럼 그리드 + 모바일 세로 스택으로 렌더하고, 카드 탭 시 TradingView 차트 아코디언 + 증권사 딥링크 3개가 펼쳐지는 실행 동선까지 완성.

**Architecture:** 백엔드는 `collectors/edgar.py` + `storage/tickers.py` 추가, `analysis/scoring.py` 에 EDGAR Item·Form 4 점수 규칙 확장, `orchestrator` 와 `json_builder` 에 picks 선별 로직. 프론트엔드는 `[종목]` 3번째 탭 + `PicksGrid`·`PicksCard`·`TradingViewWidget`·`DeeplinkButtons` 컴포넌트. 컨테이너 max-width 를 종목 탭에서만 720px 로 확장.

**Tech Stack:** Week 2a 그대로 + SEC EDGAR REST API (Form 4 Atom, 8-K RSS, User-Agent 필수) + TradingView Embed Widget (무료, key 없음) + 증권사 커스텀 URL scheme (iOS/Android).

---

## File Structure (Week 2b 결과물)

### 백엔드 (Python)

| 파일 | 책임 |
|------|------|
| `src/news_briefing/collectors/edgar.py` | SEC EDGAR 8-K + Form 4 Atom 수집 |
| `src/news_briefing/storage/tickers.py` | DART corp_code ↔ stock_code ↔ corp_name 매핑 테이블 |
| `src/news_briefing/analysis/scoring.py` (수정) | EDGAR form_type + Item 번호별 규칙 추가 |
| `src/news_briefing/analysis/picks.py` | Today's Pick 선별 로직 (국내/해외 각 N건) |
| `src/news_briefing/delivery/deeplinks.py` | 토스증권/증권플러스/네이버 URL 생성 |
| `src/news_briefing/delivery/json_builder.py` (수정) | `tabs.picks` 구조 채우기 |
| `src/news_briefing/orchestrator.py` (수정) | EDGAR 수집 + picks 선별 호출 |
| `src/news_briefing/storage/db.py` (수정) | `tickers` 테이블 스키마 추가 |
| `scripts/seed_tickers.py` | DART 기업개황 파싱으로 초기 tickers seed (수동 1회) |

### 프론트엔드 (TypeScript/React)

| 파일 | 책임 |
|------|------|
| `frontend/src/components/PicksGrid.tsx` | 2×컬럼(데스크탑)/세로 스택(모바일) 레이아웃 |
| `frontend/src/components/PicksCard.tsx` | 컴팩트 카드 + 아코디언 동작 |
| `frontend/src/components/TradingViewWidget.tsx` | iframe 임베드, 심볼 맵 |
| `frontend/src/components/DeeplinkButtons.tsx` | 국내만 딥링크 3개, 해외는 "해외 종목" 라벨 |
| `frontend/src/components/TabBar.tsx` (수정) | 3번째 종목 탭 추가 |
| `frontend/src/components/AppShell.tsx` (수정) | 종목 탭에서 max-width 720px 적용 |
| `frontend/src/app/page.tsx` (수정) | `tab === 'picks'` 분기 추가 |
| `frontend/src/lib/tradingview.ts` | ticker → TradingView 심볼 매핑 |
| `frontend/src/lib/deeplinks.ts` | 증권사 URL builder (클라이언트 미러) |
| `frontend/src/lib/types.ts` (수정) | PicksTab 노출 |

### 테스트

| 파일 | 책임 |
|------|------|
| `tests/test_edgar.py` | Atom 파싱 + HTTP mock |
| `tests/test_tickers.py` | 매핑 CRUD |
| `tests/test_scoring_edgar.py` | EDGAR form_type 가중치 |
| `tests/test_picks.py` | 선별 로직 (중복 제거 · 상위 N) |
| `tests/test_deeplinks.py` | URL 생성 |
| `tests/fixtures/edgar_form4.atom` | Form 4 샘플 |
| `tests/fixtures/edgar_8k.atom` | 8-K 샘플 |

---

## Task 1: EDGAR collector — 8-K + Form 4 Atom 파싱

**Files:**
- Create: `src/news_briefing/collectors/edgar.py`
- Create: `tests/fixtures/edgar_form4.atom`
- Create: `tests/fixtures/edgar_8k.atom`
- Create: `tests/test_edgar.py`

SEC EDGAR Atom: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4&dateb=&owner=include&count=40&output=atom` (Form 4 전체 스캔). 8-K 는 `type=8-K`. User-Agent 필수 (SEC 요건).

- [ ] **Step 1: Form 4 fixture**

`tests/fixtures/edgar_form4.atom`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Latest Filings - Form 4</title>
  <entry>
    <title>4 - NVIDIA CORP (0001045810) (Issuer)</title>
    <link href="https://www.sec.gov/Archives/edgar/data/1045810/000104581026000123/0001045810-26-000123-index.htm"/>
    <id>urn:tag:sec.gov,2026:nvda-20260421</id>
    <updated>2026-04-21T20:15:00-04:00</updated>
    <summary type="html">
      &lt;b&gt;Filed:&lt;/b&gt; 2026-04-21
      &lt;b&gt;Accession Number:&lt;/b&gt; 0001045810-26-000123
    </summary>
    <category term="4" scheme="https://www.sec.gov/" label="form type"/>
  </entry>
  <entry>
    <title>4 - TESLA INC (0001318605) (Issuer)</title>
    <link href="https://www.sec.gov/Archives/edgar/data/1318605/000131860526000200/0001318605-26-000200-index.htm"/>
    <id>urn:tag:sec.gov,2026:tsla-20260421</id>
    <updated>2026-04-21T18:00:00-04:00</updated>
    <summary type="html">&lt;b&gt;Filed:&lt;/b&gt; 2026-04-21</summary>
    <category term="4" scheme="https://www.sec.gov/" label="form type"/>
  </entry>
</feed>
```

- [ ] **Step 2: 8-K fixture**

`tests/fixtures/edgar_8k.atom`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Latest Filings - Form 8-K</title>
  <entry>
    <title>8-K - APPLE INC (0000320193)</title>
    <link href="https://www.sec.gov/Archives/edgar/data/320193/000032019326000050/0000320193-26-000050-index.htm"/>
    <id>urn:tag:sec.gov,2026:aapl-8k-20260421</id>
    <updated>2026-04-21T16:30:00-04:00</updated>
    <summary type="html">&lt;b&gt;Filed:&lt;/b&gt; 2026-04-21 Item 2.02</summary>
    <category term="8-K" scheme="https://www.sec.gov/" label="form type"/>
  </entry>
</feed>
```

- [ ] **Step 3: Failing test**

```python
# tests/test_edgar.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from news_briefing.collectors.edgar import (
    EDGAR_FORM4_URL,
    fetch_edgar_form4,
    fetch_edgar_8k,
    parse_edgar_atom,
)


def test_parse_form4(fixtures_dir: Path) -> None:
    content = (fixtures_dir / "edgar_form4.atom").read_text(encoding="utf-8")
    items = parse_edgar_atom(content, form_type="4")
    assert len(items) == 2
    nvda = items[0]
    assert nvda.source == "edgar"
    assert "NVIDIA" in nvda.company
    assert nvda.company_code == "0001045810" or nvda.company_code == ""
    assert nvda.url.startswith("https://www.sec.gov/")
    assert nvda.extra.get("form_type") == "4"


def test_parse_8k_extracts_item_numbers(fixtures_dir: Path) -> None:
    content = (fixtures_dir / "edgar_8k.atom").read_text(encoding="utf-8")
    items = parse_edgar_atom(content, form_type="8-K")
    assert items[0].extra.get("form_type") == "8-K"
    assert "2.02" in items[0].extra.get("items", "")


def test_parse_empty_returns_empty_list() -> None:
    assert parse_edgar_atom("<feed></feed>", form_type="4") == []


def test_fetch_form4_sends_user_agent(mocker) -> None:
    mock_resp = MagicMock()
    mock_resp.text = "<feed></feed>"
    mock_resp.raise_for_status = MagicMock()
    mock_get = mocker.patch(
        "news_briefing.collectors.edgar.requests.get", return_value=mock_resp
    )
    fetch_edgar_form4(user_agent="Test Agent test@example.com")
    args, kwargs = mock_get.call_args
    assert "cgi-bin/browse-edgar" in args[0]
    assert kwargs["params"]["type"] == "4"
    assert "Test Agent" in kwargs["headers"]["User-Agent"]


def test_fetch_without_user_agent_returns_empty_and_logs(caplog) -> None:
    items = fetch_edgar_form4(user_agent="")
    assert items == []
```

- [ ] **Step 4: Implement edgar.py**

```python
# src/news_briefing/collectors/edgar.py
"""SEC EDGAR 8-K + Form 4 Atom 수집기.

User-Agent 필수 (SEC policy). Rate limit 10 req/s.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

EDGAR_FORM4_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
EDGAR_8K_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}

# 제목 패턴: "4 - COMPANY NAME (0001234567) (Issuer)"
TITLE_RE = re.compile(r"^(?:\d|8)[^-]*-\s*(.+?)\s*\((\d+)\)")
ITEM_RE = re.compile(r"Item\s*(\d+\.\d+)", re.IGNORECASE)


def parse_edgar_atom(content: str, form_type: str) -> list[CollectedItem]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        log.error("EDGAR atom parse 실패: %s", e)
        return []

    items: list[CollectedItem] = []
    for entry in root.findall("a:entry", ATOM_NS):
        title_el = entry.find("a:title", ATOM_NS)
        link_el = entry.find("a:link", ATOM_NS)
        id_el = entry.find("a:id", ATOM_NS)
        updated_el = entry.find("a:updated", ATOM_NS)
        summary_el = entry.find("a:summary", ATOM_NS)

        if title_el is None or link_el is None or id_el is None:
            continue

        title = (title_el.text or "").strip()
        m = TITLE_RE.match(title)
        company = m.group(1) if m else title
        cik = m.group(2) if m else ""

        url = link_el.get("href", "")
        ext_id = (id_el.text or "").strip() or url
        published = datetime.utcnow().replace(tzinfo=None)
        if updated_el is not None and updated_el.text:
            try:
                published = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
            except Exception:
                pass

        summary_text = summary_el.text or "" if summary_el is not None else ""
        item_match = ITEM_RE.search(summary_text)
        items_str = item_match.group(1) if item_match else ""

        items.append(
            CollectedItem(
                source="edgar",
                ext_id=ext_id,
                kind="disclosure",
                title=f"{form_type} — {company}",
                url=url,
                published_at=published,
                company=company,
                company_code=cik,
                extra={"form_type": form_type, "cik": cik, "items": items_str},
            )
        )
    return items


def _fetch_atom(
    form_type: str, *, user_agent: str, count: int = 40, timeout: int = 15
) -> list[CollectedItem]:
    if not user_agent:
        log.warning("EDGAR User-Agent 없음, 수집 스킵")
        return []
    try:
        resp = requests.get(
            EDGAR_FORM4_URL,
            params={
                "action": "getcompany",
                "type": form_type,
                "dateb": "",
                "owner": "include",
                "count": count,
                "output": "atom",
            },
            headers={"User-Agent": user_agent, "Accept": "application/atom+xml"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return parse_edgar_atom(resp.text, form_type)
    except Exception as e:
        log.error("EDGAR %s 수집 실패: %s", form_type, e)
        return []


def fetch_edgar_form4(*, user_agent: str, count: int = 40) -> list[CollectedItem]:
    return _fetch_atom("4", user_agent=user_agent, count=count)


def fetch_edgar_8k(*, user_agent: str, count: int = 40) -> list[CollectedItem]:
    return _fetch_atom("8-K", user_agent=user_agent, count=count)


def fetch_all_edgar(user_agent: str) -> list[CollectedItem]:
    return fetch_edgar_form4(user_agent=user_agent) + fetch_edgar_8k(user_agent=user_agent)
```

- [ ] **Step 5: Add `edgar_user_agent` to Config + `.env.example`**

`config.py`:
```python
# Config 에 추가
edgar_user_agent: str

# load_config 에 추가
edgar_user_agent=os.environ.get("EDGAR_USER_AGENT", ""),
```

`.env.example`:
```
# SEC EDGAR (https://www.sec.gov/os/accessing-edgar-data)
# 형식: "이름/이메일" 필수. 예: "Hyunwoo Jung taesion9060@gmail.com"
EDGAR_USER_AGENT=
```

- [ ] **Step 6: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_edgar.py tests/test_config.py -v
git add src/news_briefing/collectors/edgar.py src/news_briefing/config.py .env.example tests/test_edgar.py tests/fixtures/edgar_*.atom
git commit -m "feat(collectors): SEC EDGAR 8-K + Form 4 Atom collector with User-Agent guard"
```

---

## Task 2: Tickers 매핑 테이블 (DART corp_code ↔ stock_code ↔ name)

**Files:**
- Modify: `src/news_briefing/storage/db.py` (schema)
- Create: `src/news_briefing/storage/tickers.py`
- Create: `tests/test_tickers.py`

DART `corp_code` (8자리) 와 `stock_code` (6자리) 매핑이 필요. 실시간 조회는 느리므로 DB 에 캐시. DART `corp_code.xml` zip API 로 일괄 로드 지원 (하지만 Week 2b 에서는 on-demand 캐시만).

- [ ] **Step 1: Schema 추가**

`db.py` `_SCHEMA` 끝에:
```sql
CREATE TABLE IF NOT EXISTS tickers (
    stock_code TEXT PRIMARY KEY,     -- 005930 (6자리)
    corp_code  TEXT NOT NULL,         -- 00126380 (DART 8자리)
    corp_name  TEXT NOT NULL,
    market     TEXT,                  -- 'KOSPI' | 'KOSDAQ' | 'KONEX'
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickers_corp ON tickers(corp_code);
```

- [ ] **Step 2: Failing test**

```python
# tests/test_tickers.py
from __future__ import annotations

import sqlite3

from news_briefing.storage.db import init_schema
from news_briefing.storage.tickers import (
    TickerRow,
    upsert_ticker,
    get_ticker_by_stock,
    get_ticker_by_corp,
)


def test_roundtrip(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    row = TickerRow(
        stock_code="005930", corp_code="00126380",
        corp_name="삼성전자", market="KOSPI",
    )
    upsert_ticker(memory_db, row)
    assert get_ticker_by_stock(memory_db, "005930") == row
    assert get_ticker_by_corp(memory_db, "00126380") == row


def test_miss_returns_none(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    assert get_ticker_by_stock(memory_db, "999999") is None
    assert get_ticker_by_corp(memory_db, "99999999") is None


def test_upsert_overwrites(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_ticker(memory_db, TickerRow("005930", "00126380", "OLD", "KOSPI"))
    upsert_ticker(memory_db, TickerRow("005930", "00126380", "NEW", "KOSPI"))
    row = get_ticker_by_stock(memory_db, "005930")
    assert row.corp_name == "NEW"
```

- [ ] **Step 3: Implement tickers.py**

```python
# src/news_briefing/storage/tickers.py
"""corp_code ↔ stock_code ↔ corp_name 매핑."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class TickerRow:
    stock_code: str
    corp_code: str
    corp_name: str
    market: str | None = None


def upsert_ticker(conn: sqlite3.Connection, row: TickerRow) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO tickers(stock_code, corp_code, corp_name, market, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (row.stock_code, row.corp_code, row.corp_name, row.market, now),
    )
    conn.commit()


def get_ticker_by_stock(conn: sqlite3.Connection, stock_code: str) -> TickerRow | None:
    r = conn.execute(
        "SELECT stock_code, corp_code, corp_name, market FROM tickers WHERE stock_code=?",
        (stock_code,),
    ).fetchone()
    return (
        TickerRow(r["stock_code"], r["corp_code"], r["corp_name"], r["market"])
        if r
        else None
    )


def get_ticker_by_corp(conn: sqlite3.Connection, corp_code: str) -> TickerRow | None:
    r = conn.execute(
        "SELECT stock_code, corp_code, corp_name, market FROM tickers WHERE corp_code=?",
        (corp_code,),
    ).fetchone()
    return (
        TickerRow(r["stock_code"], r["corp_code"], r["corp_name"], r["market"])
        if r
        else None
    )
```

- [ ] **Step 4: DART collector 가 stock_code 수집 시 tickers 에 upsert**

`collectors/dart.py` 의 `parse_dart_response` 는 이미 `stock_code` 를 CollectedItem 에 넣고 있음. orchestrator 에서 `upsert_ticker` 호출로 자동 채워지게 할지, 아니면 별도 `scripts/seed_tickers.py` 로 한 번에 채울지 결정.

**Week 2b 선택**: DART 수집 시 자동 upsert (가장 자연스럽고 orchestrator 만 수정). 공시가 있는 종목만 쌓이지만 그게 실제로 Today's Pick 에 노출될 후보이므로 충분.

`orchestrator.run_morning` 에 추가:
```python
from news_briefing.storage.tickers import TickerRow, upsert_ticker

# ...
for item in new_items:
    if item.source == "dart" and item.company_code:
        corp_code = (item.extra or {}).get("corp_code", "") if item.extra else ""
        # DART 응답 파싱 시 corp_code 보존 필요 (기존 parse_dart_response 확인)
```

Wait — current `parse_dart_response` 가 `corp_code` 를 `extra` 에 안 넣고 있음. `dart.py` 에 `extra={"corp_cls": ..., "corp_code": row["corp_code"]}` 로 확장 필요.

- [ ] **Step 5: Extend parse_dart_response to include corp_code in extra**

`collectors/dart.py` 수정:
```python
extra={
    "corp_cls": row.get("corp_cls", ""),
    "corp_code": row.get("corp_code", ""),
},
```

- [ ] **Step 6: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_tickers.py tests/test_dart.py -v
git add src/news_briefing/storage/db.py src/news_briefing/storage/tickers.py src/news_briefing/collectors/dart.py tests/test_tickers.py
git commit -m "feat(storage): tickers table for DART corp_code↔stock_code mapping"
```

---

## Task 3: EDGAR scoring 확장

**Files:**
- Modify: `src/news_briefing/analysis/scoring.py`
- Create: `tests/test_scoring_edgar.py`

Form 4 (내부자) + 8-K (주요 사건) 의 form_type 과 item 번호별 기본 점수.

- [ ] **Step 1: Failing test**

```python
# tests/test_scoring_edgar.py
from __future__ import annotations

from news_briefing.analysis.scoring import score_edgar


def test_form4_base_score() -> None:
    assert score_edgar(form_type="4", items="")[0] == 70  # 매수/매도 구분 전 기본


def test_8k_item_1_01_material_agreement() -> None:
    # Item 1.01 - Entry into a Material Definitive Agreement
    score, direction = score_edgar(form_type="8-K", items="1.01")
    assert score == 75
    assert direction == "positive"


def test_8k_item_2_01_acquisition() -> None:
    score, direction = score_edgar(form_type="8-K", items="2.01")
    assert score == 85
    assert direction == "mixed"


def test_8k_item_4_02_restated() -> None:
    # Item 4.02 - Non-reliance on previously issued financials
    score, direction = score_edgar(form_type="8-K", items="4.02")
    assert score == 90
    assert direction == "negative"


def test_unknown_item_falls_back_to_default_8k() -> None:
    score, _ = score_edgar(form_type="8-K", items="")
    assert score == 70


def test_unknown_form_type() -> None:
    score, direction = score_edgar(form_type="10-Q", items="")
    assert score == 45
    assert direction == "neutral"
```

- [ ] **Step 2: Implement score_edgar in scoring.py**

Append to `scoring.py`:

```python
# SIGNALS.md 2.1 해외 대응 — 8-K Item 번호별
EDGAR_ITEM_WEIGHTS: dict[str, tuple[int, Direction]] = {
    "1.01": (75, "positive"),   # Material Definitive Agreement (신규 계약)
    "1.02": (75, "negative"),   # Termination of Material Agreement
    "2.01": (85, "mixed"),      # Completion of Acquisition/Disposition
    "2.02": (80, "mixed"),      # Results of Operations (실적)
    "2.06": (95, "negative"),   # Material Impairments
    "3.01": (85, "negative"),   # Delisting Notice
    "3.02": (75, "mixed"),      # Unregistered Sales of Equity
    "4.01": (90, "negative"),   # Changes in Registrant's Certifying Accountant
    "4.02": (90, "negative"),   # Non-reliance on Previously Issued Financials
    "5.02": (70, "mixed"),      # Departure/Appointment of Directors/Officers
    "5.07": (50, "neutral"),    # Submission of Matters to Vote
    "7.01": (60, "neutral"),    # Regulation FD Disclosure
    "8.01": (60, "neutral"),    # Other Events
}


def score_edgar(*, form_type: str, items: str) -> tuple[int, Direction]:
    """SEC EDGAR form_type + items 기반 점수."""
    if form_type == "4":
        # Form 4: 매수/매도 구분은 추가 파싱 필요. 기본 70 (임원·주주 매매와 동일).
        return 70, "mixed"

    if form_type == "8-K":
        for item_code, (score, direction) in EDGAR_ITEM_WEIGHTS.items():
            if item_code in items:
                return score, direction
        return 70, "neutral"  # 8-K with unknown item

    # 그 외 form (10-K, 10-Q, DEF 14A 등)
    return 45, "neutral"
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_scoring_edgar.py -v
git add src/news_briefing/analysis/scoring.py tests/test_scoring_edgar.py
git commit -m "feat(analysis): EDGAR 8-K item + Form 4 scoring rules"
```

---

## Task 4: Today's Pick 선별 로직

**Files:**
- Create: `src/news_briefing/analysis/picks.py`
- Create: `tests/test_picks.py`

시그널 점수 상위 N 건을 국내/해외로 분리. 같은 종목(`company_code`)의 여러 공시는 최고 점수만. 결과를 `json_builder` 가 소비.

- [ ] **Step 1: Failing test**

```python
# tests/test_picks.py
from __future__ import annotations

from datetime import datetime

from news_briefing.collectors.base import CollectedItem
from news_briefing.analysis.picks import select_picks


def _mk(company="삼성전자", code="005930", score=80, source="dart", ext_id="x") -> tuple[CollectedItem, int, str]:
    it = CollectedItem(
        source=source, ext_id=ext_id, kind="disclosure",
        title="타이틀", url="https://x",
        published_at=datetime(2026, 4, 22),
        company=company, company_code=code,
    )
    return it, score, "positive"


def test_select_picks_splits_domestic_and_foreign() -> None:
    scored = [
        _mk(source="dart", code="005930", ext_id="1"),
        _mk(source="edgar", code="NVDA", ext_id="2", company="NVIDIA"),
    ]
    result = select_picks(scored, n_per_side=6)
    assert len(result.domestic) == 1
    assert len(result.foreign) == 1


def test_dedup_same_company_keeps_highest_score() -> None:
    scored = [
        _mk(code="005930", score=70, ext_id="a"),
        _mk(code="005930", score=90, ext_id="b"),
        _mk(code="005930", score=60, ext_id="c"),
    ]
    result = select_picks(scored, n_per_side=6)
    assert len(result.domestic) == 1
    assert result.domestic[0][1] == 90


def test_picks_sorted_desc_by_score() -> None:
    scored = [
        _mk(code="A", score=60, ext_id="a"),
        _mk(code="B", score=85, ext_id="b"),
        _mk(code="C", score=75, ext_id="c"),
    ]
    result = select_picks(scored, n_per_side=6)
    scores = [s for _, s, _ in result.domestic]
    assert scores == [85, 75, 60]


def test_picks_truncates_to_n_per_side() -> None:
    scored = [_mk(code=f"C{i}", score=100 - i, ext_id=str(i)) for i in range(10)]
    result = select_picks(scored, n_per_side=6)
    assert len(result.domestic) == 6
    assert [s for _, s, _ in result.domestic] == [100, 99, 98, 97, 96, 95]
```

- [ ] **Step 2: Implement picks.py**

```python
# src/news_briefing/analysis/picks.py
"""Today's Pick 선별 (DECISIONS #12).

시그널 점수 상위 N건, 같은 company_code 는 최고 점수만, 국내/해외 분리.
"""
from __future__ import annotations

from dataclasses import dataclass

from news_briefing.collectors.base import CollectedItem

ScoredSignal = tuple[CollectedItem, int, str]


@dataclass(frozen=True, slots=True)
class PicksResult:
    domestic: list[ScoredSignal]
    foreign: list[ScoredSignal]


def select_picks(
    scored: list[ScoredSignal], *, n_per_side: int = 6
) -> PicksResult:
    """국내/해외 상위 N. 같은 company_code 는 최고 점수만 남긴다."""
    best_by_key: dict[tuple[str, str], ScoredSignal] = {}
    for item, s, d in scored:
        key = (item.source.split(":")[0], item.company_code or item.company or item.ext_id)
        existing = best_by_key.get(key)
        if existing is None or s > existing[1]:
            best_by_key[key] = (item, s, d)

    domestic = [t for t in best_by_key.values() if not t[0].source.startswith("edgar")]
    foreign = [t for t in best_by_key.values() if t[0].source.startswith("edgar")]

    domestic.sort(key=lambda t: t[1], reverse=True)
    foreign.sort(key=lambda t: t[1], reverse=True)

    return PicksResult(
        domestic=domestic[:n_per_side],
        foreign=foreign[:n_per_side],
    )
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_picks.py -v
git add src/news_briefing/analysis/picks.py tests/test_picks.py
git commit -m "feat(analysis): Today's Pick selection with dedup per company"
```

---

## Task 5: 증권사 딥링크 생성기

**Files:**
- Create: `src/news_briefing/delivery/deeplinks.py`
- Create: `tests/test_deeplinks.py`
- Create: `frontend/src/lib/deeplinks.ts` (client mirror)

- [ ] **Step 1: Failing test**

```python
# tests/test_deeplinks.py
from __future__ import annotations

from news_briefing.delivery.deeplinks import build_deeplinks


def test_samsung_links() -> None:
    links = build_deeplinks("005930")
    assert links["toss"] == "supertoss://stock/005930"
    assert links["koreainvestment"].endswith("005930")
    assert "005930" in links["naver"]


def test_empty_code_returns_empty_dict() -> None:
    assert build_deeplinks("") == {}


def test_all_three_providers_present() -> None:
    links = build_deeplinks("000660")
    assert set(links.keys()) == {"toss", "koreainvestment", "naver"}
```

- [ ] **Step 2: Implement deeplinks.py**

```python
# src/news_briefing/delivery/deeplinks.py
"""증권사 앱 딥링크 생성 (F19).

국내 종목(KRX 6자리 stock_code)만 지원. 해외는 미지원.
"""
from __future__ import annotations


def build_deeplinks(stock_code: str) -> dict[str, str]:
    if not stock_code:
        return {}
    return {
        "toss": f"supertoss://stock/{stock_code}",
        "koreainvestment": f"koreainvestment://stock/{stock_code}",
        "naver": f"https://m.stock.naver.com/domestic/stock/{stock_code}/total",
    }
```

- [ ] **Step 3: Client mirror (frontend/src/lib/deeplinks.ts)**

```typescript
export function buildDeeplinks(stockCode: string): {
  toss: string
  koreainvestment: string
  naver: string
} | null {
  if (!stockCode) return null
  return {
    toss: `supertoss://stock/${stockCode}`,
    koreainvestment: `koreainvestment://stock/${stockCode}`,
    naver: `https://m.stock.naver.com/domestic/stock/${stockCode}/total`,
  }
}
```

- [ ] **Step 4: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_deeplinks.py -v
git add src/news_briefing/delivery/deeplinks.py tests/test_deeplinks.py frontend/src/lib/deeplinks.ts
git commit -m "feat(delivery): brokerage deeplinks (toss/증권플러스/naver)"
```

---

## Task 6: JSON builder — tabs.picks 추가

**Files:**
- Modify: `src/news_briefing/delivery/json_builder.py`
- Modify: `tests/test_json_builder.py`

- [ ] **Step 1: Failing test**

Add to `test_json_builder.py`:
```python
from news_briefing.analysis.picks import PicksResult

def test_picks_tab_populated() -> None:
    from news_briefing.analysis.picks import select_picks
    data = build_briefing_json(
        date=datetime(2026, 4, 22),
        scored_signals=[
            (_item("공시1", "1"), 85, "positive"),
        ],
        economy_news=[],
        picks=select_picks([(_item("공시1", "1"), 85, "positive")], n_per_side=6),
    )
    assert "picks" in data["tabs"]
    assert len(data["tabs"]["picks"]["domestic"]) == 1
    assert data["tabs"]["picks"]["domestic"][0]["score"] == 85
    assert data["tabs"]["picks"]["foreign"] == []


def test_picks_tab_absent_when_no_picks() -> None:
    data = build_briefing_json(
        date=datetime(2026, 4, 22),
        scored_signals=[],
        economy_news=[],
    )
    # picks 가 None 이면 tabs.picks 구조는 빈 배열로 포함
    assert data["tabs"]["picks"]["domestic"] == []
    assert data["tabs"]["picks"]["foreign"] == []
```

- [ ] **Step 2: Extend build_briefing_json**

```python
from news_briefing.analysis.picks import PicksResult  # add import

def build_briefing_json(
    *,
    date: datetime,
    scored_signals: list[tuple[CollectedItem, int, str]],
    economy_news: list[CollectedItem],
    glossary: dict[str, dict] | None = None,
    term_ids_by_id: dict[str, str] | None = None,
    picks: PicksResult | None = None,
) -> dict:
    # ... (existing body) ...

    picks_tab = {"domestic": [], "foreign": []}
    if picks:
        picks_tab["domestic"] = [
            _signal_to_dict(it, s, d, term_ids_by_id)
            for it, s, d in picks.domestic
        ]
        picks_tab["foreign"] = [
            _signal_to_dict(it, s, d, term_ids_by_id)
            for it, s, d in picks.foreign
        ]

    return {
        "date": date.strftime("%Y-%m-%d"),
        "generatedAt": datetime.now(UTC).isoformat(),
        "version": SCHEMA_VERSION,
        "hero": hero,
        "tabs": {
            "current": {...},
            "economy": {...},
            "picks": picks_tab,
        },
        "glossary": glossary or {},
    }
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_json_builder.py -v
git add src/news_briefing/delivery/json_builder.py tests/test_json_builder.py
git commit -m "feat(delivery): briefing JSON includes tabs.picks structure"
```

---

## Task 7: Orchestrator — EDGAR 수집 + picks 선별 통합

**Files:**
- Modify: `src/news_briefing/orchestrator.py`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Add EDGAR fetch + picks computation**

In `run_morning` after existing DART/RSS fetch:
```python
from news_briefing.analysis.picks import select_picks
from news_briefing.collectors.edgar import fetch_all_edgar
from news_briefing.storage.tickers import TickerRow, upsert_ticker
from news_briefing.analysis.scoring import score_edgar

# Week 2b: EDGAR 수집
if cfg.edgar_user_agent:
    edgar_items = fetch_all_edgar(cfg.edgar_user_agent)
    for it in edgar_items:
        if not is_seen(conn, it.source, it.ext_id):
            new_items.append(it)
            mark_seen(conn, it.source, it.ext_id)

# EDGAR scoring: form_type + items 사용
for it in edgar_items_only_in_new:
    form_type = (it.extra or {}).get("form_type", "")
    items_str = (it.extra or {}).get("items", "")
    s, d = score_edgar(form_type=form_type, items=items_str)
    scored.append((it, s, d))

# DART 공시마다 tickers upsert
for item in new_items:
    if item.source == "dart":
        corp_code = (item.extra or {}).get("corp_code", "")
        if corp_code and item.company_code:
            upsert_ticker(conn, TickerRow(
                stock_code=item.company_code,
                corp_code=corp_code,
                corp_name=item.company or "",
                market=None,
            ))

# 선별
picks = select_picks(scored, n_per_side=6)

# JSON 에 전달
briefing = build_briefing_json(
    date=now, scored_signals=scored, economy_news=fresh_news,
    glossary=glossary_map, term_ids_by_id=term_ids_by_id,
    picks=picks,
)
```

- [ ] **Step 2: 새 테스트**

```python
def test_morning_writes_picks_tab(tmp_path, mocker) -> None:
    cfg = _cfg(tmp_path)
    domestic_sample = CollectedItem(
        source="dart", ext_id="d1", kind="disclosure",
        title="자기주식취득결정", url="x",
        published_at=datetime(2026, 4, 22),
        company="삼성전자", company_code="005930",
        extra={"corp_code": "00126380", "corp_cls": "Y"},
    )
    foreign_sample = CollectedItem(
        source="edgar", ext_id="e1", kind="disclosure",
        title="8-K — NVIDIA CORP", url="x",
        published_at=datetime(2026, 4, 22),
        company="NVIDIA CORP", company_code="0001045810",
        extra={"form_type": "8-K", "items": "2.01"},
    )
    mocker.patch("news_briefing.orchestrator.fetch_dart_list", return_value=[domestic_sample])
    mocker.patch("news_briefing.orchestrator.fetch_all_edgar", return_value=[foreign_sample])
    mocker.patch("news_briefing.orchestrator.fetch_all_rss", return_value=[])
    mocker.patch("news_briefing.orchestrator.summarize", return_value="")
    mocker.patch("news_briefing.orchestrator._send_kakao")

    # EDGAR UA 있게 config 업데이트
    # ... (Config 재생성 helper)
```

- [ ] **Step 3: Pass + commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_orchestrator.py -v
git add src/news_briefing/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator integrates EDGAR + picks selection + tickers upsert"
```

---

## Task 8: Frontend — types + PicksTab 노출

**Files:**
- Modify: `frontend/src/lib/types.ts` (이미 `picks?` 로 optional, 필수로 변경 or `picks` 를 그대로 optional 유지)

- [ ] **Step 1: Types OK** (Week 2a 에서 이미 `picks?: PicksTab` 로 선언됨)

No code change needed, just verify `PicksTab` has `domestic` and `foreign` arrays.

---

## Task 9: TradingView widget 컴포넌트

**Files:**
- Create: `frontend/src/lib/tradingview.ts`
- Create: `frontend/src/components/TradingViewWidget.tsx`

TradingView 공식 Embed Widget 은 iframe 로드 방식. 심볼 매핑: 국내 `KRX:{6자리}`, 미국 `NASDAQ:{ticker}` / `NYSE:{ticker}`.

Week 2b 는 종목 source 가 DART(stock_code) 와 EDGAR(CIK만 있음, ticker 는 별도 필요) — EDGAR ticker 는 어떻게 얻나?

**결정**: 
- DART: `stock_code` → `KRX:{stock_code}` 직결
- EDGAR: `company` 에서 잘라낸 이름으로는 부정확. SEC 는 CIK-to-ticker 매핑 파일 제공 (`https://www.sec.gov/files/company_tickers.json`). Week 2b 에 별도 seed 스크립트로 `tickers` 테이블에 CIK↔ticker 저장. 또는 간단히 유명 종목 하드코딩 (NVDA, AAPL, TSLA, MSFT, GOOG, AMZN, META) 로 시작.

**간단 시작**: 하드코딩 매핑 `CIK_TO_TICKER` 10~20개. SEC 파일 파싱은 Week 2b 후반 또는 Week 3로 이관.

- [ ] **Step 1: tradingview.ts**

```typescript
// frontend/src/lib/tradingview.ts
import type { SignalItem } from '@/lib/types'

// CIK → 미국 ticker 하드코딩 (Week 2b 초기). SEC company_tickers.json 로딩은 후속.
const CIK_TICKER: Record<string, { ticker: string; exchange: 'NASDAQ' | 'NYSE' }> = {
  '0001045810': { ticker: 'NVDA', exchange: 'NASDAQ' },
  '0000320193': { ticker: 'AAPL', exchange: 'NASDAQ' },
  '0001318605': { ticker: 'TSLA', exchange: 'NASDAQ' },
  '0000789019': { ticker: 'MSFT', exchange: 'NASDAQ' },
  '0001652044': { ticker: 'GOOGL', exchange: 'NASDAQ' },
  '0001018724': { ticker: 'AMZN', exchange: 'NASDAQ' },
  '0001326801': { ticker: 'META', exchange: 'NASDAQ' },
  '0000062709': { ticker: 'BRK.A', exchange: 'NYSE' },
  '0000051143': { ticker: 'IBM', exchange: 'NYSE' },
}

export function resolveTradingViewSymbol(signal: SignalItem): string | null {
  if (signal.source === 'dart' && signal.companyCode) {
    return `KRX:${signal.companyCode}`
  }
  if (signal.source === 'edgar' && signal.companyCode) {
    const m = CIK_TICKER[signal.companyCode.padStart(10, '0')]
    if (m) return `${m.exchange}:${m.ticker}`
  }
  return null
}
```

- [ ] **Step 2: TradingViewWidget.tsx**

```tsx
'use client'

import { useEffect, useRef } from 'react'

export function TradingViewWidget({
  symbol,
  height = 300,
}: {
  symbol: string
  height?: number
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const script = document.createElement('script')
    script.src =
      'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      symbols: [[symbol, symbol]],
      chartOnly: true,
      width: '100%',
      height,
      locale: 'ko',
      colorTheme: document.documentElement.classList.contains('dark')
        ? 'dark'
        : 'light',
      autosize: false,
      showVolume: false,
      hideDateRanges: false,
      isTransparent: false,
      noTimeScale: false,
    })
    containerRef.current.appendChild(script)
    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = ''
      }
    }
  }, [symbol, height])

  return (
    <div
      ref={containerRef}
      className="tradingview-widget-container"
      style={{ height, marginTop: 16, marginBottom: 16 }}
    />
  )
}
```

- [ ] **Step 3: Build + commit**

```bash
cd /c/GitHub/daily-news/frontend && npm run build
git add frontend/src/lib/tradingview.ts frontend/src/components/TradingViewWidget.tsx
git commit -m "feat(frontend): TradingView widget with KRX/NASDAQ/NYSE symbol mapping"
```

---

## Task 10: Deeplink buttons 컴포넌트

**Files:**
- Create: `frontend/src/components/DeeplinkButtons.tsx`

- [ ] **Step 1: Implement**

```tsx
'use client'

import type { SignalItem } from '@/lib/types'
import { buildDeeplinks } from '@/lib/deeplinks'

export function DeeplinkButtons({ signal }: { signal: SignalItem }) {
  if (signal.source === 'edgar' || signal.scope === 'foreign') {
    return (
      <div
        className="text-center"
        style={{
          fontSize: 12,
          fontWeight: 500,
          color: 'var(--text-tertiary)',
          marginTop: 12,
        }}
      >
        해외 종목
      </div>
    )
  }

  if (!signal.companyCode) return null
  const links = buildDeeplinks(signal.companyCode)
  if (!links) return null

  const btnStyle = {
    flex: 1,
    background: 'var(--bg-inset)',
    color: 'var(--text-secondary)',
    padding: '10px 12px',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    textAlign: 'center' as const,
  }

  return (
    <div className="flex gap-2" style={{ marginTop: 12 }}>
      <a href={links.toss} style={btnStyle}>
        토스증권
      </a>
      <a href={links.koreainvestment} style={btnStyle}>
        증권플러스
      </a>
      <a href={links.naver} target="_blank" rel="noopener" style={btnStyle}>
        네이버증권
      </a>
    </div>
  )
}
```

- [ ] **Step 2: Build + commit**

```bash
cd /c/GitHub/daily-news/frontend && npm run build
git add frontend/src/components/DeeplinkButtons.tsx
git commit -m "feat(frontend): DeeplinkButtons with toss/증권플러스/naver for domestic"
```

---

## Task 11: PicksCard (컴팩트 카드 + 아코디언)

**Files:**
- Create: `frontend/src/components/PicksCard.tsx`

- [ ] **Step 1: Implement**

```tsx
'use client'

import { useState } from 'react'
import { resolveTradingViewSymbol } from '@/lib/tradingview'
import type { Direction, SignalItem } from '@/lib/types'
import { DeeplinkButtons } from './DeeplinkButtons'
import { TradingViewWidget } from './TradingViewWidget'

const TONE: Record<Direction, string> = {
  positive: '#3182F6',
  negative: '#F04452',
  mixed: '#F79A34',
  neutral: '#8B95A1',
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('ko-KR', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

export function PicksCard({
  signal,
  dict,
}: {
  signal: SignalItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  const [open, setOpen] = useState(false)
  const color = TONE[signal.direction]
  const symbol = resolveTradingViewSymbol(signal)
  const time = formatTime(signal.time)

  return (
    <article
      onClick={() => setOpen((v) => !v)}
      className="cursor-pointer"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card-sm)',
        padding: '16px 18px',
      }}
    >
      <div className="flex items-center" style={{ gap: 7, marginBottom: 8 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
          }}
        />
        <span className="ml-auto" style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
          {time}
        </span>
      </div>
      <h4 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
        {signal.company || '—'}
      </h4>
      <p
        style={{
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--text-secondary)',
          marginTop: 4,
          lineHeight: 1.45,
        }}
      >
        {signal.headline}
      </p>

      {open && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border-subtle)' }}
        >
          {symbol ? (
            <TradingViewWidget symbol={symbol} height={220} />
          ) : (
            <p
              className="text-center"
              style={{ fontSize: 12, color: 'var(--text-tertiary)', padding: 20 }}
            >
              차트 심볼을 찾을 수 없어요
            </p>
          )}
          <a
            href={signal.url}
            target="_blank"
            rel="noopener"
            onClick={(e) => e.stopPropagation()}
            className="block text-center"
            style={{
              background: 'var(--text-primary)',
              color: 'var(--bg-card)',
              padding: '12px',
              borderRadius: 'var(--radius-btn)',
              fontSize: 13,
              fontWeight: 700,
              marginTop: 8,
            }}
          >
            {dict['cta.openOriginal']}
          </a>
          <DeeplinkButtons signal={signal} />
        </div>
      )}
    </article>
  )
}
```

- [ ] **Step 2: Build + commit**

```bash
cd /c/GitHub/daily-news/frontend && npm run build
git add frontend/src/components/PicksCard.tsx
git commit -m "feat(frontend): PicksCard compact with accordion chart + deeplinks"
```

---

## Task 12: PicksGrid (2×컬럼/스택 레이아웃)

**Files:**
- Create: `frontend/src/components/PicksGrid.tsx`

- [ ] **Step 1: Implement**

```tsx
'use client'

import type { PicksTab } from '@/lib/types'
import { PicksCard } from './PicksCard'

export function PicksGrid({
  picks,
  dict,
}: {
  picks: PicksTab
  dict: import('@/lib/i18n/ko').Dict
}) {
  const renderColumn = (label: string, signals: typeof picks.domestic) => (
    <div>
      <h3
        style={{
          fontSize: 20,
          fontWeight: 700,
          color: 'var(--text-primary)',
          padding: '0 4px',
          marginBottom: 4,
        }}
      >
        {label}
      </h3>
      <div
        style={{
          fontSize: 13,
          color: 'var(--text-tertiary)',
          padding: '0 4px',
          marginBottom: 12,
        }}
      >
        Today's Pick · {signals.length}건
      </div>
      {signals.length === 0 ? (
        <p
          className="text-center"
          style={{
            fontSize: 13,
            color: 'var(--text-tertiary)',
            padding: '40px 10px',
          }}
        >
          오늘은 조용해요
        </p>
      ) : (
        <div className="flex flex-col" style={{ gap: 8 }}>
          {signals.map((s) => (
            <PicksCard key={s.id} signal={s} dict={dict} />
          ))}
        </div>
      )}
    </div>
  )

  return (
    <div
      className="px-4"
      style={{
        maxWidth: 'var(--container-picks)',
        margin: '0 auto',
      }}
    >
      <div className="picks-grid">
        {renderColumn('국내', picks.domestic)}
        {renderColumn('해외', picks.foreign)}
      </div>
      <style jsx>{`
        .picks-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 28px;
        }
        @media (min-width: 720px) {
          .picks-grid {
            grid-template-columns: 1fr 1fr;
            gap: 14px;
          }
        }
      `}</style>
    </div>
  )
}
```

- [ ] **Step 2: Build + commit**

```bash
cd /c/GitHub/daily-news/frontend && npm run build
git add frontend/src/components/PicksGrid.tsx
git commit -m "feat(frontend): PicksGrid 2×column desktop / stacked mobile"
```

---

## Task 13: TabBar 3탭 + page.tsx picks 분기 + AppShell width 확장

**Files:**
- Modify: `frontend/src/components/TabBar.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/AppShell.tsx`

- [ ] **Step 1: TabBar 에 'picks' 추가**

```tsx
const tabs: { key: Tab; label: string }[] = [
  { key: 'current', label: dict['tab.current'] },
  { key: 'economy', label: dict['tab.economy'] },
  { key: 'picks', label: dict['tab.picks'] },
]
```

`min-width: 100px` 은 유지하되 3개 탭이면 너비 줄여야 모바일 fit — `80px` 로.

- [ ] **Step 2: page.tsx 에 `tab === 'picks'` 분기**

```tsx
if (tab === 'picks') {
  const picks = briefing.tabs.picks ?? { domestic: [], foreign: [] }
  return <PicksGrid picks={picks} dict={dict} />
}
```

- [ ] **Step 3: AppShell 에서 picks 탭일 때 max-width 확장**

```tsx
// AppShell 안에서 useSearchParams 로 탭 읽고 containerWidth 결정:
const tab = parseTabFromSearch(sp)
const maxWidth = tab === 'picks'
  ? 'var(--container-picks)'
  : 'var(--container-briefing)'
```

header/main 의 maxWidth 를 동적으로.

- [ ] **Step 4: ScopeFilter — picks 탭에서 숨기기**

```tsx
// ScopeFilter 시작에:
if (tab === 'picks') return null
```

- [ ] **Step 5: Build + commit**

```bash
cd /c/GitHub/daily-news/frontend && npm run build
git add frontend/src/
git commit -m "feat(frontend): 3-tab with picks + page branching + dynamic container width"
```

---

## Task 14: E2E verify + test run + push

- [ ] **Step 1: Backend dry-run** (실제 오늘 데이터 + EDGAR)

`.env` 에 `EDGAR_USER_AGENT` 채워져 있으면 실제 수집 테스트. 없으면 DART 만.

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m news_briefing morning --dry-run
```

Expected: briefing JSON 에 `tabs.picks.domestic` 채워짐.

- [ ] **Step 2: frontend build + local serve**

```bash
cd /c/GitHub/daily-news/frontend && npm run build
cd out && python -m http.server 8000
```

브라우저 검증:
- [종목] 탭 표시, 클릭 시 PicksGrid 렌더
- 데스크탑에서 2×컬럼, 모바일(F12)에서 세로 스택
- 카드 탭 → TradingView 차트 펼침
- 국내 카드 하단 3개 딥링크 버튼, 해외 카드는 "해외 종목" 라벨
- 다크 모드에서도 차트 colorTheme 따라감

- [ ] **Step 3: pytest 전체**

```bash
.venv/Scripts/python.exe -m pytest 2>&1 | tail -5
```

Expected: Week 1 62 + Week 2a 26 + Week 2b 추가분 모두 pass.

- [ ] **Step 4: ruff**

```bash
.venv/Scripts/python.exe -m ruff check src tests
```

- [ ] **Step 5: 최종 commit + push**

```bash
git push
```

---

## Week 2b Definition of Done

- [ ] 종목 탭 진입 시 국내/해외 2×컬럼 그리드 렌더 (데스크탑), 모바일은 세로 스택
- [ ] 국내 카드 탭 시 TradingView 차트 (KRX:종목코드) 렌더
- [ ] 해외 카드 탭 시 TradingView 차트 (NASDAQ:/NYSE:) 렌더 — 하드코딩된 상위 9종목 한정
- [ ] 국내 카드에 증권사 딥링크 3개 (토스·증권플러스·네이버) 노출
- [ ] 해외 카드는 "해외 종목" 라벨 (딥링크 미지원)
- [ ] SEC EDGAR Form 4/8-K 가 해외 Today's Pick 에 포함됨 (User-Agent 설정 시)
- [ ] 같은 종목이 여러 공시로 중복 노출되지 않음 (company_code 기준 dedup)
- [ ] 탭 3개 (시사·경제·종목) 전환·URL 쿼리 동기화
- [ ] `CLAUDE.md` P1 금칙어("추천") 가 UI·코드 어디에도 없음
- [ ] `DECISIONS.md` #12 재고 조건이 해당 문서에 명시됨 (이미 됨)

---

## Self-Review

**Spec coverage (ROADMAP Week 2b 작업 항목 10개):**

1. SEC EDGAR 수집기 → Task 1 ✅
2. EDGAR 스코어링 → Task 3 ✅
3. DART corp_code↔stock_code 매핑 → Task 2 ✅
4. 종목 탭 UI → Task 13 ✅
5. 종목 그리드 컴포넌트 → Task 12 ✅
6. 종목 컴팩트 카드 → Task 11 ✅
7. TradingView 위젯 → Task 9 ✅
8. 증권사 딥링크 → Task 5 + 10 ✅
9. Today's Pick 선별 로직 → Task 4 ✅
10. 카톡 메시지 업데이트 → **의도적으로 스킵** (Week 2b 는 링크 유지, 사용량 관찰 후 Week 3 에서 `?tab=picks` 전환 결정 — DECISIONS #12)

**Placeholder scan:** 없음.

**Type consistency:** `PicksResult` (Python) ↔ `PicksTab` (TypeScript) 필드명 일치 (domestic / foreign).

**Risks:**
- EDGAR User-Agent 미설정 시 해외 탭 empty → 빈 상태 카피로 graceful
- CIK_TICKER 하드코딩 9개만 — 그 외 EDGAR 종목은 차트가 "심볼 없음"으로 표시 (Week 3+ 에서 SEC company_tickers.json 파싱으로 확장)
- TradingView iframe 이 CSP 및 광고 차단기와 충돌할 수 있음 — Vercel 배포 시 테스트
