# 공시 본문 분석 단계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 실적·합병 공시의 본문에서 정량 사실을 추출해 `score`·`direction` 을 규칙으로 재산정한다. 컨센서스에 부합한(정보량 없는) 실적 공시를 picks 상위에서 강등시킨다.

**Architecture:** 수집(`filing_body`·`earnings_surprise`) → 추출(`filing_facts`, LLM 은 여기서만) → 판단(`filing_score`, 순수 함수) 3계층. `orchestrator` 의 점수 산정 단계에서 게이팅으로 상위 25건만 본문을 연다. 추출 실패 시 기존 제목 점수로 폴백하므로 최악의 경우에도 현행과 동일하다.

**Tech Stack:** Python 3.11+, requests, yfinance, Supabase(`llm_cache` 재사용), Claude CLI(`_call_claude`), pytest, ruff

**Spec:** `docs/superpowers/specs/2026-07-09-filing-analysis-design.md`

## Global Constraints

- Python 3.11+ (`match` 문, `|` 타입 힌트 사용). 모든 모듈 상단에 `from __future__ import annotations`
- 줄 길이 100자. `ruff format` + `ruff check --fix` 통과 필수
- 함수·모듈 docstring 은 **한국어**. 변수·함수명은 영어
- 코멘트는 왜(why)를 설명한다. 무엇(what)은 코드가 말하게 한다
- **`anthropic` SDK 직접 호출 금지, `ANTHROPIC_API_KEY` 설정 금지.** LLM 은 반드시 `news_briefing.analysis.llm._call_claude` 경유
- 외부 API 호출은 항상 timeout: 본문 수집 15초, LLM 45초
- 한 수집기의 실패가 파이프라인 전체를 멈추지 않는다. 개별 `try/except` + `log.error` 후 빈 결과로 계속 진행
- 네트워크 실호출 테스트는 `@pytest.mark.integration` 으로 분리 (기본 실행 제외)
- 커밋은 Task 단위로 끊는다. `Co-Authored-By` 트레일러는 넣지 않는다

## File Structure

| 파일 | 책임 |
|---|---|
| `src/news_briefing/analysis/filing_facts.py` | `FilingFacts` 데이터클래스, 공시 유형 분류, 게이팅 선별, LLM 추출 |
| `src/news_briefing/analysis/filing_score.py` | `FilingFacts` → `(score, direction)`. **순수 함수. LLM·네트워크 없음** |
| `src/news_briefing/collectors/filing_body.py` | DART `document.xml` zip 해제·태그 제거, EDGAR 8-K `EX-99.1` 본문 |
| `src/news_briefing/collectors/earnings_surprise.py` | SEC CIK→티커 매핑, yfinance 서프라이즈 조회 |
| `src/news_briefing/orchestrator.py` | 3단계 점수 산정에 게이팅·재점수 연결 (수정) |
| `src/news_briefing/analysis/picks_outcomes.py` | 원장 행에 `facts_json` 추가 (수정) |
| `scripts/supabase_schema.sql` | `pick_outcomes.facts_json` 컬럼 (수정) |

`FilingFacts` 데이터클래스는 `filing_facts.py` 에 둔다. `filing_score.py` 는 이 데이터클래스만
import 하며, LLM 호출은 `filing_facts.py` 안의 **함수 내부 lazy import** 로 격리해
`filing_score` 가 순수하게 유지되도록 한다.

---

### Task 1: `FilingFacts` 모델과 순수 재점수 함수

판단 로직을 가장 먼저, 네트워크·LLM 없이 짓는다. 이후 모든 태스크가 이 타입에 의존한다.

**Files:**
- Create: `src/news_briefing/analysis/filing_facts.py` (데이터클래스만. 추출기는 Task 4)
- Create: `src/news_briefing/analysis/filing_score.py`
- Test: `tests/test_filing_score.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `FilingFacts` (frozen dataclass, 아래 필드 전부)
  - `rescore(facts: FilingFacts) -> tuple[int, str] | None` — 사실이 불충분하면 `None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_filing_score.py`:

```python
"""filing_score 순수 재점수 규칙 — 경계값 중심."""
from __future__ import annotations

import pytest

from news_briefing.analysis.filing_facts import FilingFacts
from news_briefing.analysis.filing_score import rescore


def _earnings(**kw) -> FilingFacts:
    return FilingFacts(kind="earnings", scope="foreign", **kw)


@pytest.mark.parametrize(
    ("surprise", "expected"),
    [
        (12.0, (88, "positive")),
        (10.0, (88, "positive")),   # 경계 포함
        (7.0, (80, "positive")),
        (5.0, (80, "positive")),    # 경계 포함
        (4.9, (55, "neutral")),
        (0.0, (55, "neutral")),
        (-4.9, (55, "neutral")),
        (-5.0, (80, "negative")),   # 경계 포함
        (-9.9, (80, "negative")),
        (-10.0, (88, "negative")),  # 경계 포함
        (-30.0, (88, "negative")),
    ],
)
def test_surprise_bands(surprise, expected):
    assert rescore(_earnings(surprise_pct=surprise)) == expected


def test_turnaround_beats_yoy():
    """전환은 YoY 보다 강한 신호 — 먼저 판정한다."""
    facts = FilingFacts(
        kind="earnings", scope="domestic", turnaround="적자전환",
        operating_income_yoy_pct=50.0,
    )
    assert rescore(facts) == (92, "negative")


def test_surplus_turnaround():
    facts = FilingFacts(kind="earnings", scope="domestic", turnaround="흑자전환")
    assert rescore(facts) == (90, "positive")


@pytest.mark.parametrize(
    ("yoy", "expected"),
    [
        (45.0, (85, "positive")),
        (30.0, (85, "positive")),   # 경계 포함
        (29.9, (75, "positive")),
        (10.0, (75, "positive")),   # 경계 포함
        (9.9, (55, "neutral")),
        (-9.9, (55, "neutral")),
        (-10.0, (75, "negative")),  # 경계 포함
        (-29.9, (75, "negative")),
        (-30.0, (85, "negative")),  # 경계 포함
    ],
)
def test_domestic_yoy_bands(yoy, expected):
    facts = FilingFacts(kind="earnings", scope="domestic", operating_income_yoy_pct=yoy)
    assert rescore(facts) == expected


def test_surprise_wins_over_yoy():
    """서프라이즈가 있으면 YoY 는 보지 않는다 (컨센서스 대비가 우선)."""
    facts = FilingFacts(
        kind="earnings", scope="foreign", surprise_pct=12.0,
        operating_income_yoy_pct=-50.0,
    )
    assert rescore(facts) == (88, "positive")


def test_target_high_premium():
    facts = FilingFacts(kind="merger", scope="foreign", is_target=True, premium_pct=35.0)
    assert rescore(facts) == (90, "positive")


def test_target_mid_premium():
    facts = FilingFacts(kind="merger", scope="foreign", is_target=True, premium_pct=15.0)
    assert rescore(facts) == (82, "positive")


def test_target_unknown_premium():
    """프리미엄 미상이어도 피인수 자체가 호재 — 다만 점수는 낮춘다."""
    facts = FilingFacts(kind="merger", scope="domestic", is_target=True)
    assert rescore(facts) == (75, "positive")


def test_acquirer_is_mixed():
    facts = FilingFacts(kind="merger", scope="foreign", is_target=False, premium_pct=40.0)
    assert rescore(facts) == (70, "mixed")


def test_insufficient_facts_returns_none():
    """사실이 없으면 None — 호출부가 제목 점수로 폴백한다."""
    assert rescore(FilingFacts(kind="earnings", scope="domestic")) is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_filing_score.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_briefing.analysis.filing_facts'`

- [ ] **Step 3: 데이터클래스 구현**

`src/news_briefing/analysis/filing_facts.py`:

```python
"""공시 본문에서 추출한 정량 사실 (SPEC 2026-07-09 §5).

추출기(LLM 호출)는 Task 4 에서 이 모듈에 추가된다. 여기서는 타입만 정의해
`filing_score` 가 LLM·네트워크 의존 없이 이 모듈을 import 할 수 있게 한다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

FilingKind = str  # "earnings" | "merger"
Scope = str       # "domestic" | "foreign"


@dataclass(frozen=True, slots=True)
class FilingFacts:
    """한 공시에서 뽑은 사실. 결측은 모두 None — 부분 추출을 허용한다."""

    kind: FilingKind
    scope: Scope

    # 실적 — 해외 (컨센서스 대비)
    eps_estimate: float | None = None
    eps_reported: float | None = None
    surprise_pct: float | None = None

    # 실적 — 국내 (전년동기 대비). 금액 단위는 원.
    revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    revenue_yoy_pct: float | None = None
    operating_income_yoy_pct: float | None = None
    turnaround: str | None = None  # "흑자전환" | "적자전환"

    # 합병·인수
    acquirer: str | None = None
    target: str | None = None
    deal_value: float | None = None
    premium_pct: float | None = None
    consideration: str | None = None  # "cash" | "stock" | "mixed"
    is_target: bool = False           # 이 공시를 낸 회사가 피인수 주체인가

    def to_json_dict(self) -> dict:
        """None 필드를 제거한 dict — llm_cache·facts_json 직렬화용."""
        return {k: v for k, v in asdict(self).items() if v is not None and v is not False}
```

- [ ] **Step 4: 재점수 함수 구현**

`src/news_briefing/analysis/filing_score.py`:

```python
"""FilingFacts → (score, direction) 재점수 (SPEC 2026-07-09 §6).

순수 함수만 둔다. LLM·네트워크·DB 를 쓰지 않으므로 픽스처만으로 전 규칙을
테스트할 수 있고, 임계값 변경의 영향을 백테스트로 측정할 수 있다.

임계값 주의: 아래 경계값은 업계 관행에 따른 초기값이며 이 시스템의 픽 성과로
검증된 값이 아니다. pick_outcomes.facts_json 이 쌓이면 구간별 alpha 를 집계해
조정한다. 변경 시 사용자 승인 + DECISIONS.md 기록 (CLAUDE.md).
"""
from __future__ import annotations

from news_briefing.analysis.filing_facts import FilingFacts

Direction = str  # "positive" | "negative" | "mixed" | "neutral"


def _band(value: float, strong: float, weak: float, strong_score: int, weak_score: int,
          neutral_score: int) -> tuple[int, Direction]:
    """대칭 구간 판정. |value| 가 strong 이상이면 강, weak 이상이면 약, 그 아래는 중립."""
    if value >= strong:
        return strong_score, "positive"
    if value >= weak:
        return weak_score, "positive"
    if value > -weak:
        return neutral_score, "neutral"
    if value > -strong:
        return weak_score, "negative"
    return strong_score, "negative"


def _score_earnings(f: FilingFacts) -> tuple[int, Direction] | None:
    # 컨센서스 대비가 있으면 최우선 — YoY 는 시장이 이미 알던 정보를 포함한다.
    if f.surprise_pct is not None:
        return _band(f.surprise_pct, strong=10.0, weak=5.0,
                     strong_score=88, weak_score=80, neutral_score=55)

    # 전환은 연속 지표로 표현되지 않는 이산 사건 — YoY 보다 먼저 본다.
    if f.turnaround == "적자전환":
        return 92, "negative"
    if f.turnaround == "흑자전환":
        return 90, "positive"

    if f.operating_income_yoy_pct is not None:
        return _band(f.operating_income_yoy_pct, strong=30.0, weak=10.0,
                     strong_score=85, weak_score=75, neutral_score=55)

    return None


def _score_merger(f: FilingFacts) -> tuple[int, Direction] | None:
    # 인수 주체의 주가 영향은 양방향(시너지 vs 고가 인수) — mixed 로 둔다.
    if not f.is_target:
        return 70, "mixed"

    if f.premium_pct is None:
        return 75, "positive"
    if f.premium_pct >= 30.0:
        return 90, "positive"
    if f.premium_pct >= 10.0:
        return 82, "positive"
    return 75, "positive"


def rescore(facts: FilingFacts) -> tuple[int, Direction] | None:
    """사실 기반 재점수. 사실이 불충분하면 None — 호출부가 제목 점수로 폴백한다."""
    if facts.kind == "earnings":
        return _score_earnings(facts)
    if facts.kind == "merger":
        return _score_merger(facts)
    return None
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_filing_score.py -q`
Expected: PASS (30개 내외)

- [ ] **Step 6: 린트 후 커밋**

```bash
ruff format src/news_briefing/analysis/filing_facts.py src/news_briefing/analysis/filing_score.py tests/test_filing_score.py
ruff check --fix src/news_briefing/analysis/ tests/test_filing_score.py
pytest tests/test_filing_score.py -q
git add src/news_briefing/analysis/filing_facts.py src/news_briefing/analysis/filing_score.py tests/test_filing_score.py
git commit -m "feat(filing): FilingFacts 모델과 순수 재점수 함수

서프라이즈·YoY·전환·프리미엄 구간으로 direction 을 확정한다.
컨센서스 부합 구간(-5~+5%)은 55점으로 강등해 picks 상위 잠식을 막는다."
```

---

### Task 2: 공시 본문 수집기

**Files:**
- Create: `src/news_briefing/collectors/filing_body.py`
- Create: `tests/fixtures/dart_document.xml`
- Test: `tests/test_filing_body.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `strip_xml_tags(raw: str) -> str`
  - `unzip_dart_document(payload: bytes) -> str` — zip bytes → 태그 제거된 텍스트
  - `fetch_dart_body(api_key: str, rcept_no: str, *, timeout: int = 15) -> str` — 실패 시 `""`
  - `fetch_edgar_press_release(url: str, *, user_agent: str, timeout: int = 15) -> str` — 실패 시 `""`

- [ ] **Step 1: 픽스처 작성**

`tests/fixtures/dart_document.xml` — 실제 DART 본문의 축약본:

```xml
<?xml version="1.0" encoding="utf-8"?>
<DOCUMENT>
  <BODY>
    <TITLE>영업(잠정)실적(공정공시)</TITLE>
    <TABLE>
      <TR><TD>매출액</TD><TD>1,234,567</TD></TR>
      <TR><TD>영업이익</TD><TD>98,765</TD></TR>
    </TABLE>
  </BODY>
</DOCUMENT>
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_filing_body.py`:

```python
"""공시 본문 수집기 — zip 해제·태그 제거. 네트워크 없이."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from news_briefing.collectors.filing_body import (
    fetch_dart_body,
    strip_xml_tags,
    unzip_dart_document,
)

FIXTURE = Path(__file__).parent / "fixtures" / "dart_document.xml"


def test_strip_xml_tags_collapses_whitespace():
    raw = "<A>  매출액 </A>\n\n<B>1,234</B>"
    assert strip_xml_tags(raw) == "매출액 1,234"


def test_unzip_dart_document_decodes_cp949():
    """DART 본문은 cp949 인코딩이다. utf-8 로 읽으면 깨진다."""
    raw = FIXTURE.read_text(encoding="utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("20260708000567.xml", raw.encode("cp949"))

    text = unzip_dart_document(buf.getvalue())

    assert "영업(잠정)실적" in text
    assert "1,234,567" in text
    assert "<TABLE>" not in text


def test_unzip_invalid_payload_returns_empty():
    """zip 이 아니면 예외를 던지지 않고 빈 문자열 — 파이프라인을 멈추지 않는다."""
    assert unzip_dart_document(b"not a zip") == ""


def test_fetch_dart_body_without_key_returns_empty():
    assert fetch_dart_body("", "20260708000567") == ""
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `pytest tests/test_filing_body.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_briefing.collectors.filing_body'`

- [ ] **Step 4: 구현**

`src/news_briefing/collectors/filing_body.py`:

```python
"""공시 본문 수집 — DART document.xml, EDGAR 8-K 첨부 보도자료.

네트워크 IO 만 담당한다. 사실 추출은 analysis/filing_facts.py 가 한다.

DART 는 zip(내부 XML, cp949) 을 반환한다. EDGAR 8-K 의 실적 보도자료는
filing index 의 EX-99.x 첨부에 들어있다.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile

import requests

log = logging.getLogger(__name__)

DART_DOCUMENT_URL = "https://opendart.fss.or.kr/api/document.xml"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# LLM 프롬프트에 넣을 본문 상한. 실적표는 앞부분에 나오므로 앞에서 자른다.
MAX_BODY_CHARS = 12_000


def strip_xml_tags(raw: str) -> str:
    """태그를 제거하고 공백을 접는다."""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", raw)).strip()


def unzip_dart_document(payload: bytes) -> str:
    """DART document.xml 응답(zip) → 태그 제거된 본문. 실패 시 빈 문자열."""
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            names = z.namelist()
            if not names:
                return ""
            raw = z.read(names[0]).decode("cp949", errors="replace")
    except Exception as e:
        log.error("DART 본문 zip 해제 실패: %s", e)
        return ""
    return strip_xml_tags(raw)[:MAX_BODY_CHARS]


def fetch_dart_body(api_key: str, rcept_no: str, *, timeout: int = 15) -> str:
    """접수번호로 DART 본문을 가져온다. 실패 시 빈 문자열."""
    if not api_key or not rcept_no:
        return ""
    try:
        resp = requests.get(
            DART_DOCUMENT_URL,
            params={"crtfc_key": api_key, "rcept_no": rcept_no},
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception as e:
        log.error("DART 본문 수집 실패(rcept_no=%s): %s", rcept_no, e)
        return ""
    return unzip_dart_document(resp.content)


def fetch_edgar_press_release(url: str, *, user_agent: str, timeout: int = 15) -> str:
    """8-K filing index 에서 EX-99.x 보도자료 본문을 가져온다. 실패 시 빈 문자열.

    8-K 본문 자체는 'Item 2.02 ... see Exhibit 99.1' 식의 참조뿐이라 숫자가 없다.
    실제 실적 표는 첨부 보도자료에 있다.
    """
    if not url or not user_agent:
        return ""
    headers = {"User-Agent": user_agent}
    try:
        index = requests.get(url, headers=headers, timeout=timeout)
        index.raise_for_status()
        m = re.search(r'href="([^"]+ex99[^"]*\.htm[l]?)"', index.text, re.IGNORECASE)
        if not m:
            return ""
        href = m.group(1)
        exhibit_url = href if href.startswith("http") else f"https://www.sec.gov{href}"
        doc = requests.get(exhibit_url, headers=headers, timeout=timeout)
        doc.raise_for_status()
    except Exception as e:
        log.error("EDGAR 보도자료 수집 실패(%s): %s", url, e)
        return ""
    return strip_xml_tags(doc.text)[:MAX_BODY_CHARS]
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_filing_body.py -q`
Expected: PASS (4개)

- [ ] **Step 6: 린트 후 커밋**

```bash
ruff format src/news_briefing/collectors/filing_body.py tests/test_filing_body.py
ruff check --fix src/news_briefing/collectors/filing_body.py tests/test_filing_body.py
pytest tests/test_filing_body.py -q
git add src/news_briefing/collectors/filing_body.py tests/test_filing_body.py tests/fixtures/dart_document.xml
git commit -m "feat(filing): 공시 본문 수집기 (DART zip, EDGAR EX-99)

DART 는 cp949 zip 을 반환하고, 8-K 실적 숫자는 본문이 아니라
첨부 보도자료(EX-99.x)에 있다. 실패는 빈 문자열로 흡수한다."
```

---

### Task 3: 해외 실적 서프라이즈 수집기

해외 실적은 본문 파싱도 LLM 도 필요 없다. yfinance 가 컨센서스 대비 서프라이즈를 직접 준다.
EDGAR 는 CIK 만 주므로 SEC `company_tickers.json` 으로 티커를 얻는다(10,418건, 무료).

**Files:**
- Create: `src/news_briefing/collectors/earnings_surprise.py`
- Test: `tests/test_earnings_surprise.py`

**Interfaces:**
- Consumes: `FilingFacts` (Task 1)
- Produces:
  - `cik_to_ticker(cik: str, *, user_agent: str) -> str | None` (프로세스 내 캐시)
  - `fetch_surprise(ticker: str) -> tuple[float | None, float | None, float | None]` —
    `(eps_estimate, eps_reported, surprise_pct)`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_earnings_surprise.py`:

```python
"""해외 실적 서프라이즈 — 네트워크는 모두 monkeypatch."""
from __future__ import annotations

import pytest

from news_briefing.collectors import earnings_surprise as es


@pytest.fixture(autouse=True)
def _clear_cache():
    es._TICKER_CACHE.clear()
    yield
    es._TICKER_CACHE.clear()


def test_cik_to_ticker_zero_pads(monkeypatch):
    """EDGAR atom 의 CIK 는 0 패딩이 없을 수도 있다. 양쪽을 모두 맞춘다."""
    monkeypatch.setattr(es, "_fetch_ticker_map", lambda ua: {"0000320193": "AAPL"})
    assert es.cik_to_ticker("0000320193", user_agent="x") == "AAPL"
    assert es.cik_to_ticker("320193", user_agent="x") == "AAPL"


def test_cik_to_ticker_unknown_returns_none(monkeypatch):
    monkeypatch.setattr(es, "_fetch_ticker_map", lambda ua: {})
    assert es.cik_to_ticker("0000000001", user_agent="x") is None


def test_fetch_surprise_picks_latest_reported(monkeypatch):
    """가장 최근 '보고된' 분기를 쓴다. 미래 예정 분기(Reported EPS=NaN)는 건너뛴다."""
    import math

    import pandas as pd

    df = pd.DataFrame(
        {
            "EPS Estimate": [1.89, 1.94, 2.67],
            "Reported EPS": [math.nan, 2.01, 2.84],
            "Surprise(%)": [math.nan, 3.46, 6.34],
        },
        index=pd.to_datetime(["2026-07-30", "2026-04-30", "2026-01-29"]),
    )
    monkeypatch.setattr(es, "_earnings_dates", lambda t: df)

    est, rep, sur = es.fetch_surprise("AAPL")

    assert est == pytest.approx(1.94)
    assert rep == pytest.approx(2.01)
    assert sur == pytest.approx(3.46)


def test_fetch_surprise_all_nan_returns_none(monkeypatch):
    import math

    import pandas as pd

    df = pd.DataFrame(
        {"EPS Estimate": [1.0], "Reported EPS": [math.nan], "Surprise(%)": [math.nan]},
        index=pd.to_datetime(["2026-07-30"]),
    )
    monkeypatch.setattr(es, "_earnings_dates", lambda t: df)
    assert es.fetch_surprise("AAPL") == (None, None, None)


def test_fetch_surprise_swallows_errors(monkeypatch):
    def boom(_t):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(es, "_earnings_dates", boom)
    assert es.fetch_surprise("AAPL") == (None, None, None)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_earnings_surprise.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_briefing.collectors.earnings_surprise'`

- [ ] **Step 3: 구현**

`src/news_briefing/collectors/earnings_surprise.py`:

```python
"""해외 실적 서프라이즈 — yfinance earnings_dates.

8-K Item 2.02 는 '실적을 발표했다'만 알려준다. 컨센서스 대비 몇 % 인지는
yfinance 가 EPS Estimate·Reported EPS·Surprise(%) 로 무료 제공한다.
본문 파싱도 LLM 호출도 필요 없는 경로다.

EDGAR atom 은 티커가 아니라 CIK 를 주므로 SEC company_tickers.json 으로 매핑한다.
"""
from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

# 프로세스 수명 동안만 유지. 하루 1회 실행이라 영속 캐시가 필요 없다.
_TICKER_CACHE: dict[str, str] = {}


def _fetch_ticker_map(user_agent: str) -> dict[str, str]:
    """SEC 공개 매핑 → {10자리 0패딩 CIK: 티커}."""
    resp = requests.get(SEC_TICKER_MAP_URL, headers={"User-Agent": user_agent}, timeout=15)
    resp.raise_for_status()
    return {
        str(row["cik_str"]).zfill(10): str(row["ticker"]).upper()
        for row in resp.json().values()
        if row.get("ticker")
    }


def cik_to_ticker(cik: str, *, user_agent: str) -> str | None:
    """CIK → 티커. 실패 시 None."""
    if not cik or not user_agent:
        return None
    if not _TICKER_CACHE:
        try:
            _TICKER_CACHE.update(_fetch_ticker_map(user_agent))
        except Exception as e:
            log.error("SEC 티커 매핑 수집 실패: %s", e)
            return None
    return _TICKER_CACHE.get(cik.strip().zfill(10))


def _earnings_dates(ticker: str):
    """yfinance 호출부 — 테스트에서 monkeypatch 하기 위해 분리."""
    import yfinance as yf  # noqa: PLC0415 — 무거운 import 를 호출 시점으로 미룬다

    return yf.Ticker(ticker).earnings_dates


def fetch_surprise(ticker: str) -> tuple[float | None, float | None, float | None]:
    """가장 최근 '보고된' 분기의 (추정 EPS, 실제 EPS, 서프라이즈%). 실패 시 (None, None, None).

    earnings_dates 는 미래 예정 분기도 포함하며 그 행의 Reported EPS 는 NaN 이다.
    """
    if not ticker:
        return None, None, None
    try:
        import math

        df = _earnings_dates(ticker)
        if df is None or df.empty:
            return None, None, None
        for _, row in df.iterrows():
            reported = row.get("Reported EPS")
            surprise = row.get("Surprise(%)")
            if reported is None or surprise is None:
                continue
            if math.isnan(float(reported)) or math.isnan(float(surprise)):
                continue
            estimate = row.get("EPS Estimate")
            est = None if estimate is None or math.isnan(float(estimate)) else float(estimate)
            return est, float(reported), float(surprise)
    except Exception as e:
        log.error("서프라이즈 조회 실패(%s): %s", ticker, e)
    return None, None, None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_earnings_surprise.py -q`
Expected: PASS (5개)

- [ ] **Step 5: 린트 후 커밋**

```bash
ruff format src/news_briefing/collectors/earnings_surprise.py tests/test_earnings_surprise.py
ruff check --fix src/news_briefing/collectors/earnings_surprise.py tests/test_earnings_surprise.py
pytest tests/test_earnings_surprise.py -q
git add src/news_briefing/collectors/earnings_surprise.py tests/test_earnings_surprise.py
git commit -m "feat(filing): 해외 실적 서프라이즈 수집기 (yfinance + SEC CIK 매핑)

해외 실적은 본문 파싱도 LLM 도 필요 없다. yfinance 가 컨센서스 대비
서프라이즈를 직접 준다. EDGAR 의 CIK 는 SEC company_tickers.json 으로 매핑."
```

---

### Task 4: 유형 분류·게이팅·LLM 추출

**Files:**
- Modify: `src/news_briefing/analysis/filing_facts.py` (Task 1 의 데이터클래스 아래에 추가)
- Test: `tests/test_filing_facts.py`

**Interfaces:**
- Consumes: `FilingFacts`(Task 1), `filing_body`(Task 2), `earnings_surprise`(Task 3),
  `storage.cache.cache_get/cache_put`
- Produces:
  - `classify_filing(item: CollectedItem) -> str | None` — `"earnings"|"merger"|None`
  - `select_for_analysis(scored, *, min_score=70, limit=25) -> list[CollectedItem]`
  - `extract_facts(item, kind, *, conn, cfg) -> FilingFacts | None`

`scored` 의 타입은 기존 관례를 따른다: `list[tuple[CollectedItem, int, str]]`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_filing_facts.py`:

```python
"""유형 분류와 게이팅 — LLM·네트워크 없이."""
from __future__ import annotations

from datetime import datetime

from news_briefing.analysis.filing_facts import (
    classify_filing,
    parse_facts_json,
    select_for_analysis,
)
from news_briefing.collectors.base import CollectedItem


def _item(title: str, source: str = "dart", **extra) -> CollectedItem:
    return CollectedItem(
        source=source, ext_id=title, kind="disclosure", title=title,
        url="", published_at=datetime(2026, 7, 9), extra=extra,
    )


def test_classify_domestic_earnings():
    assert classify_filing(_item("영업(잠정)실적(공정공시)")) == "earnings"


def test_classify_domestic_merger():
    assert classify_filing(_item("회사합병 결정")) == "merger"


def test_classify_edgar_earnings_by_item_code():
    item = _item("8-K — APPLE INC", source="edgar", form_type="8-K", items="2.02")
    assert classify_filing(item) == "earnings"


def test_classify_edgar_merger_by_item_code():
    item = _item("8-K — FOO INC", source="edgar", form_type="8-K", items="2.01")
    assert classify_filing(item) == "merger"


def test_classify_unrelated_returns_none():
    assert classify_filing(_item("분기보고서")) is None
    assert classify_filing(_item("8-K — X", source="edgar", form_type="4", items="")) is None


def test_select_for_analysis_filters_and_caps():
    """유형·최소점수로 거르고, 점수 상위 limit 건만 남긴다."""
    scored = [
        (_item("영업(잠정)실적 A"), 85, "mixed"),
        (_item("회사합병 결정 B"), 80, "mixed"),
        (_item("영업(잠정)실적 C"), 65, "mixed"),   # min_score 미달
        (_item("분기보고서 D"), 95, "neutral"),      # 유형 불일치
    ]
    picked = select_for_analysis(scored, min_score=70, limit=25)
    assert [i.title for i in picked] == ["영업(잠정)실적 A", "회사합병 결정 B"]


def test_select_for_analysis_respects_limit():
    scored = [(_item(f"영업(잠정)실적 {i}"), 70 + i, "mixed") for i in range(10)]
    picked = select_for_analysis(scored, min_score=70, limit=3)
    assert len(picked) == 3
    assert picked[0].title == "영업(잠정)실적 9"  # 점수 내림차순


def test_parse_facts_json_domestic_earnings():
    raw = '{"operating_income_yoy_pct": 42.5, "turnaround": null, "revenue": 1234.0}'
    facts = parse_facts_json(raw, kind="earnings", scope="domestic")
    assert facts is not None
    assert facts.operating_income_yoy_pct == 42.5
    assert facts.turnaround is None
    assert facts.kind == "earnings"


def test_parse_facts_json_strips_code_fence():
    raw = '```json\n{"premium_pct": 30.0, "is_target": true}\n```'
    facts = parse_facts_json(raw, kind="merger", scope="domestic")
    assert facts is not None
    assert facts.premium_pct == 30.0
    assert facts.is_target is True


def test_parse_facts_json_invalid_returns_none():
    assert parse_facts_json("not json", kind="earnings", scope="domestic") is None


def test_parse_facts_json_ignores_unknown_keys():
    """LLM 이 스키마에 없는 키를 넣어도 TypeError 로 죽지 않는다."""
    raw = '{"surprise_pct": 5.0, "hallucinated_field": 1}'
    facts = parse_facts_json(raw, kind="earnings", scope="foreign")
    assert facts is not None
    assert facts.surprise_pct == 5.0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_filing_facts.py -q`
Expected: FAIL — `ImportError: cannot import name 'classify_filing'`

- [ ] **Step 3: `filing_facts.py` 에 추가 구현**

Task 1 의 데이터클래스 아래에 이어붙인다. 파일 상단 import 도 아래 블록에 맞게 갱신한다.

```python
"""(모듈 docstring 은 Task 1 것을 아래로 교체)

공시 본문에서 정량 사실을 추출한다 (SPEC 2026-07-09 §4·§5).

LLM 은 '본문에 있는 숫자를 옮겨적는 일'만 한다. 해석도 추론도 하지 않으므로
할루시네이션의 여지가 구조적으로 없다. 추출 결과는 llm_cache 에 캐싱해
재실행 시 본문 수집과 LLM 호출을 둘 다 건너뛴다.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, fields

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

CACHE_TASK = "filing_facts"

# 게이팅 상한 — 하루 LLM 호출 상한과 같다. 해외 실적은 LLM 을 쓰지 않으므로
# 실제 호출은 이보다 적다.
DEFAULT_LIMIT = 25
DEFAULT_MIN_SCORE = 70

_EARNINGS_KEYWORDS = ("영업(잠정)실적", "매출액또는손익구조", "결산실적")
_MERGER_KEYWORDS = ("합병", "영업양수", "영업양도", "주식교환")

# 8-K Item 코드 — scoring.EDGAR_ITEM_WEIGHTS 와 같은 출처(SIGNALS.md 2.1)
_EDGAR_EARNINGS_ITEMS = ("2.02",)
_EDGAR_MERGER_ITEMS = ("2.01", "1.01")


def classify_filing(item: CollectedItem) -> str | None:
    """본문 분석 대상 유형. 대상이 아니면 None."""
    extra = item.extra or {}
    if item.source == "edgar":
        if extra.get("form_type") != "8-K":
            return None
        items_str = extra.get("items", "")
        if any(code in items_str for code in _EDGAR_EARNINGS_ITEMS):
            return "earnings"
        if any(code in items_str for code in _EDGAR_MERGER_ITEMS):
            return "merger"
        return None

    title = item.title
    if any(k in title for k in _EARNINGS_KEYWORDS):
        return "earnings"
    if any(k in title for k in _MERGER_KEYWORDS):
        return "merger"
    return None


def select_for_analysis(
    scored: list[tuple[CollectedItem, int, str]],
    *,
    min_score: int = DEFAULT_MIN_SCORE,
    limit: int = DEFAULT_LIMIT,
) -> list[CollectedItem]:
    """분석 대상 유형이면서 제목 점수 상위 limit 건만 고른다.

    DART 는 룩백 창에 수천 건이 유입된다. 전건 본문 수집은 불가능하고 불필요하다.
    """
    candidates = [(it, s) for it, s, _d in scored if s >= min_score and classify_filing(it)]
    candidates.sort(key=lambda t: t[1], reverse=True)
    return [it for it, _s in candidates[:limit]]


def parse_facts_json(raw: str, *, kind: str, scope: str) -> FilingFacts | None:
    """LLM 출력(JSON) → FilingFacts. 스키마 밖 키는 버린다. 실패 시 None."""
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:])
    if text.endswith("```"):
        text = "\n".join(text.splitlines()[:-1])
    text = text.strip()

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            log.warning("filing_facts JSON 파싱 실패")
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            log.warning("filing_facts JSON 파싱 실패")
            return None

    if not isinstance(obj, dict):
        return None

    allowed = {f.name for f in fields(FilingFacts)} - {"kind", "scope"}
    clean = {k: v for k, v in obj.items() if k in allowed and v is not None}
    try:
        return FilingFacts(kind=kind, scope=scope, **clean)
    except TypeError as e:
        log.warning("filing_facts 필드 불일치: %s", e)
        return None


_EARNINGS_PROMPT = """\
너는 공시 본문에서 숫자를 옮겨적는 추출기다. 해석·추론·예측을 하지 않는다.
본문에 명시되지 않은 값은 반드시 null 로 둔다.

아래 실적 공시 본문에서 다음을 추출해 JSON 객체만 반환한다(마크다운·설명 없이).

{
  "revenue": 매출액(원 단위 숫자) 또는 null,
  "operating_income": 영업이익(원 단위 숫자) 또는 null,
  "net_income": 당기순이익(원 단위 숫자) 또는 null,
  "revenue_yoy_pct": 매출 전년동기대비 증감률(%) 또는 null,
  "operating_income_yoy_pct": 영업이익 전년동기대비 증감률(%) 또는 null,
  "turnaround": "흑자전환" 또는 "적자전환" 또는 null
}

규칙:
- 단위 표기(백만원·억원)를 원 단위로 환산한다.
- 증감률이 본문에 없고 당기·전기 값이 모두 있으면 (당기-전기)/|전기|*100 으로 계산한다.
- 전기가 적자이고 당기가 흑자면 turnaround="흑자전환", 그 반대면 "적자전환".

## 본문
"""

_MERGER_PROMPT = """\
너는 공시 본문에서 사실을 옮겨적는 추출기다. 해석·추론·예측을 하지 않는다.
본문에 명시되지 않은 값은 반드시 null 로 둔다.

아래 합병·인수 공시 본문에서 다음을 추출해 JSON 객체만 반환한다(마크다운·설명 없이).

{
  "acquirer": 인수 주체 회사명 또는 null,
  "target": 피인수 대상 회사명 또는 null,
  "deal_value": 거래 총액(원 단위 숫자) 또는 null,
  "premium_pct": 인수가의 시장가 대비 프리미엄(%) 또는 null,
  "consideration": "cash" 또는 "stock" 또는 "mixed" 또는 null,
  "is_target": 이 공시를 낸 회사가 피인수 대상이면 true, 인수 주체면 false
}

## 공시 주체 회사명
{filer}

## 본문
"""


def _extract_with_llm(body: str, *, kind: str, scope: str, filer: str) -> FilingFacts | None:
    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    if kind == "earnings":
        prompt = _EARNINGS_PROMPT + body
    else:
        prompt = _MERGER_PROMPT.replace("{filer}", filer or "(미상)") + body

    try:
        raw = _call_claude(prompt, timeout=45, model="sonnet")
    except Exception as e:
        log.error("filing_facts LLM 호출 실패: %s", e)
        return None
    return parse_facts_json(raw, kind=kind, scope=scope)


def extract_facts(
    item: CollectedItem,
    kind: str,
    *,
    conn=None,
    dart_api_key: str = "",
    edgar_user_agent: str = "",
) -> FilingFacts | None:
    """공시 하나에서 사실을 추출한다. 실패 시 None — 호출부가 제목 점수로 폴백한다.

    해외 실적은 yfinance 가 서프라이즈를 직접 주므로 본문도 LLM 도 쓰지 않는다.
    나머지는 본문 → LLM 추출. 결과는 llm_cache 에 ext_id 키로 캐싱한다.
    """
    from news_briefing.collectors.earnings_surprise import cik_to_ticker, fetch_surprise
    from news_briefing.collectors.filing_body import fetch_dart_body, fetch_edgar_press_release
    from news_briefing.storage.cache import cache_get, cache_put

    is_foreign = item.source == "edgar"
    scope = "foreign" if is_foreign else "domestic"

    # 해외 실적 — LLM 불필요 경로
    if is_foreign and kind == "earnings":
        ticker = cik_to_ticker((item.extra or {}).get("cik", ""), user_agent=edgar_user_agent)
        if not ticker:
            return None
        est, rep, sur = fetch_surprise(ticker)
        if sur is None:
            return None
        return FilingFacts(
            kind=kind, scope=scope, eps_estimate=est, eps_reported=rep, surprise_pct=sur
        )

    cache_key = item.ext_id
    if conn is not None:
        try:
            cached = cache_get(conn, CACHE_TASK, cache_key)
            if cached:
                return parse_facts_json(cached, kind=kind, scope=scope)
        except Exception as e:
            log.debug("filing_facts 캐시 조회 실패: %s", e)

    if is_foreign:
        body = fetch_edgar_press_release(item.url, user_agent=edgar_user_agent)
    else:
        body = fetch_dart_body(dart_api_key, item.ext_id)
    if not body:
        return None

    facts = _extract_with_llm(body, kind=kind, scope=scope, filer=item.company)
    if facts is None:
        return None

    if conn is not None:
        try:
            cache_put(
                conn, CACHE_TASK, cache_key, json.dumps(facts.to_json_dict()), "sonnet"
            )
        except Exception as e:
            log.debug("filing_facts 캐시 저장 실패: %s", e)
    return facts
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_filing_facts.py tests/test_filing_score.py -q`
Expected: PASS (전부)

- [ ] **Step 5: 린트 후 커밋**

```bash
ruff format src/news_briefing/analysis/filing_facts.py tests/test_filing_facts.py
ruff check --fix src/news_briefing/analysis/filing_facts.py tests/test_filing_facts.py
pytest tests/test_filing_facts.py -q
git add src/news_briefing/analysis/filing_facts.py tests/test_filing_facts.py
git commit -m "feat(filing): 유형 분류·게이팅·LLM 사실 추출

DART 룩백 창의 수천 건 중 실적·합병 유형이면서 제목 점수 상위 25건만
본문을 연다. 해외 실적은 yfinance 경로라 LLM 을 쓰지 않는다.
추출 결과는 llm_cache 에 캐싱해 재실행 시 본문·LLM 을 모두 건너뛴다."
```

---

### Task 5: orchestrator 연결

**Files:**
- Modify: `src/news_briefing/orchestrator.py:259-279` (3단계 점수 산정)
- Test: `tests/test_filing_pipeline.py`

**Interfaces:**
- Consumes: `select_for_analysis`, `extract_facts`, `rescore`
- Produces: `apply_filing_analysis(scored, *, conn, cfg) -> list[tuple[CollectedItem, int, str]]`
  — `filing_facts.py` 가 아니라 `orchestrator.py` 에 두지 않고 **`analysis/filing_facts.py` 에
  둔다** (orchestrator 를 얇게 유지). `item.extra["facts"]` 를 스탬프한 새 리스트를 반환한다.

`CollectedItem` 은 `frozen=True` 지만 `extra` 는 가변 dict 이므로 그 자리에서 갱신할 수 있다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_filing_pipeline.py`:

```python
"""apply_filing_analysis — 재점수·폴백·스탬프."""
from __future__ import annotations

from datetime import datetime

from news_briefing.analysis import filing_facts as ff
from news_briefing.analysis.filing_facts import FilingFacts, apply_filing_analysis
from news_briefing.collectors.base import CollectedItem


def _item(title: str, ext_id: str = "1") -> CollectedItem:
    return CollectedItem(
        source="dart", ext_id=ext_id, kind="disclosure", title=title,
        url="", published_at=datetime(2026, 7, 9), extra={},
    )


def test_rescores_and_stamps_facts(monkeypatch):
    item = _item("영업(잠정)실적(공정공시)")
    monkeypatch.setattr(
        ff, "extract_facts",
        lambda it, kind, **kw: FilingFacts(
            kind="earnings", scope="domestic", turnaround="적자전환"
        ),
    )

    out = apply_filing_analysis([(item, 85, "mixed")], conn=None)

    assert out == [(item, 92, "negative")]
    assert item.extra["facts"]["turnaround"] == "적자전환"


def test_falls_back_to_title_score_when_extraction_fails(monkeypatch):
    """추출 실패 시 현행과 동일 — 결코 더 나빠지지 않는다."""
    item = _item("영업(잠정)실적(공정공시)")
    monkeypatch.setattr(ff, "extract_facts", lambda it, kind, **kw: None)

    out = apply_filing_analysis([(item, 85, "mixed")], conn=None)

    assert out == [(item, 85, "mixed")]
    assert "facts" not in item.extra


def test_untargeted_filings_pass_through(monkeypatch):
    """분석 대상이 아닌 공시는 손대지 않는다."""
    def _boom(*a, **k):
        raise AssertionError("대상이 아닌 공시에 추출을 시도했다")

    monkeypatch.setattr(ff, "extract_facts", _boom)
    item = _item("분기보고서")

    assert apply_filing_analysis([(item, 45, "neutral")], conn=None) == [(item, 45, "neutral")]


def test_extraction_error_does_not_break_pipeline(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("DART down")

    monkeypatch.setattr(ff, "extract_facts", _boom)
    item = _item("영업(잠정)실적(공정공시)")

    assert apply_filing_analysis([(item, 85, "mixed")], conn=None) == [(item, 85, "mixed")]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_filing_pipeline.py -q`
Expected: FAIL — `ImportError: cannot import name 'apply_filing_analysis'`

- [ ] **Step 3: `filing_facts.py` 에 `apply_filing_analysis` 추가**

파일 끝에 덧붙인다.

```python
def apply_filing_analysis(
    scored: list[tuple[CollectedItem, int, str]],
    *,
    conn=None,
    dart_api_key: str = "",
    edgar_user_agent: str = "",
    min_score: int = DEFAULT_MIN_SCORE,
    limit: int = DEFAULT_LIMIT,
) -> list[tuple[CollectedItem, int, str]]:
    """게이팅 → 사실 추출 → 재점수. 실패한 건은 제목 점수를 그대로 유지한다.

    추출된 사실은 item.extra["facts"] 에 스탬프해 hot_issues·UI·성과 원장이 함께 쓴다.
    """
    from news_briefing.analysis.filing_score import rescore  # noqa: PLC0415

    targets = {it.ext_id: it for it in select_for_analysis(scored, min_score=min_score, limit=limit)}
    if not targets:
        return scored

    rescored: dict[str, tuple[int, str]] = {}
    for ext_id, item in targets.items():
        kind = classify_filing(item)
        if not kind:
            continue
        try:
            facts = extract_facts(
                item, kind, conn=conn,
                dart_api_key=dart_api_key, edgar_user_agent=edgar_user_agent,
            )
        except Exception as e:
            # 한 건의 실패가 나머지를 막지 않는다 (CLAUDE.md 에러 처리 원칙)
            log.error("filing_facts 추출 실패(%s): %s", item.title, e)
            continue
        if facts is None:
            continue
        result = rescore(facts)
        if result is None:
            continue
        item.extra["facts"] = facts.to_json_dict()
        rescored[ext_id] = result

    log.info("filing_analysis: 대상 %d건, 재점수 %d건", len(targets), len(rescored))

    return [
        (it, *rescored[it.ext_id]) if it.ext_id in rescored else (it, s, d)
        for it, s, d in scored
    ]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_filing_pipeline.py -q`
Expected: PASS (4개)

- [ ] **Step 5: orchestrator 배선**

`src/news_briefing/orchestrator.py` 의 import 블록(20행 부근)에 추가:

```python
from news_briefing.analysis.filing_facts import apply_filing_analysis
```

3단계 끝(`scored.append((it, s, d))` 로 끝나는 for 루프 바로 다음)에 삽입:

```python
        # 3-b. 공시 본문 분석 — 실적·합병 상위 N건의 direction 을 사실로 확정
        #      (제목만으로는 서프라이즈 +12% 와 -12% 가 같은 mixed 85점이 된다)
        with _timed("3-b. 공시 본문 분석"):
            scored = apply_filing_analysis(
                scored,
                conn=conn,
                dart_api_key=cfg.dart_api_key,
                edgar_user_agent=cfg.edgar_user_agent,
            )
```

- [ ] **Step 6: 전체 테스트 + 린트 후 커밋**

```bash
ruff format src/news_briefing/analysis/filing_facts.py src/news_briefing/orchestrator.py tests/test_filing_pipeline.py
ruff check --fix src/news_briefing/ tests/
pytest -q
git add src/news_briefing/analysis/filing_facts.py src/news_briefing/orchestrator.py tests/test_filing_pipeline.py
git commit -m "feat(filing): orchestrator 3단계에 본문 분석 연결

제목 점수 직후 실적·합병 상위 25건의 사실을 추출해 재점수한다.
추출 실패는 제목 점수를 그대로 유지하므로 최악의 경우 현행과 동일하다."
```

---

### Task 6: `facts_json` 원장 적재 (스키마 변경)

임계값 재조정의 근거를 남긴다. 이 태스크가 없으면 §6 의 재고 조건을 이행할 수 없다.

**⚠️ 스키마 변경 — CLAUDE.md P4 에 따라 실행 전 사용자 승인을 받는다.**
`ALTER TABLE` 은 Supabase MCP `apply_migration` 이 아니라 아래 SQL 을 사용자가 직접
실행하거나, 승인 후 에이전트가 적용한다.

**Files:**
- Modify: `scripts/supabase_schema.sql`
- Modify: `src/news_briefing/analysis/picks_outcomes.py:101-140` (`extract_outcome_rows`)
- Modify: `src/news_briefing/analysis/filing_facts.py` (`attach_facts_to_issues` 추가)
- Modify: `src/news_briefing/orchestrator.py` (issues 에 facts 부착)
- Test: `tests/test_picks_outcomes.py` (기존 파일에 추가), `tests/test_filing_pipeline.py` (추가)

**Interfaces:**
- Consumes: `item.extra["facts"]` (Task 5 가 스탬프)
- Produces:
  - `attach_facts_to_issues(issues: list[dict], scored, *, scope: str) -> list[dict]`
  - `pick_outcomes` 행의 `facts_json` (JSON 문자열 또는 `None`)

`hot_issues` 는 LLM 출력이라 `CollectedItem` 과의 직접 연결이 끊긴다. **종목코드/티커로
재결합**한다. `hot_issues.py` 는 손대지 않는다 — LLM 프롬프트·검증 로직과 무관한 관심사이므로
`filing_facts.py` 의 순수 함수로 분리하고 orchestrator 가 호출한다.

국내 pick 의 `ticker` 는 6자리 종목코드이고 `CollectedItem.company_code` 와 같은 값이다.
해외는 `company_code` 가 CIK 이므로 `extra["ticker"]` (Task 5 에서 해외 실적 경로가 스탬프)
로 맞춘다. 매칭 실패는 `facts` 없음으로 두고 넘어간다.

- [ ] **Step 0: 해외 경로가 티커를 스탬프하도록 보강**

`filing_facts.extract_facts` 의 해외 실적 분기에서, `FilingFacts` 반환 직전에 티커를 남긴다
(해외 pick 재결합의 유일한 열쇠다):

```python
        item.extra["ticker"] = ticker
        return FilingFacts(
            kind=kind, scope=scope, eps_estimate=est, eps_reported=rep, surprise_pct=sur
        )
```

- [ ] **Step 1: 재결합 함수의 실패하는 테스트 작성**

`tests/test_filing_pipeline.py` 끝에 추가:

```python
def test_attach_facts_to_issues_matches_domestic_by_company_code():
    from news_briefing.analysis.filing_facts import attach_facts_to_issues

    item = CollectedItem(
        source="dart", ext_id="1", kind="disclosure", title="영업(잠정)실적",
        url="", published_at=datetime(2026, 7, 9), company_code="005930",
        extra={"facts": {"kind": "earnings", "operating_income_yoy_pct": 42.5}},
    )
    issues = [{"asset": "반도체", "picks": [{"ticker": "005930"}, {"ticker": "000660"}]}]

    out = attach_facts_to_issues(issues, [(item, 85, "positive")], scope="domestic")

    assert out[0]["picks"][0]["facts"]["operating_income_yoy_pct"] == 42.5
    assert "facts" not in out[0]["picks"][1]  # 매칭 실패는 조용히 건너뛴다


def test_attach_facts_to_issues_matches_foreign_by_ticker():
    from news_briefing.analysis.filing_facts import attach_facts_to_issues

    item = CollectedItem(
        source="edgar", ext_id="2", kind="disclosure", title="8-K — Apple",
        url="", published_at=datetime(2026, 7, 9), company_code="0000320193",
        extra={"ticker": "AAPL", "facts": {"kind": "earnings", "surprise_pct": 6.34}},
    )
    issues = [{"asset": "빅테크", "picks": [{"ticker": "aapl"}]}]

    out = attach_facts_to_issues(issues, [(item, 88, "positive")], scope="foreign")

    assert out[0]["picks"][0]["facts"]["surprise_pct"] == 6.34
```

- [ ] **Step 2: 재결합 함수 구현**

`src/news_briefing/analysis/filing_facts.py` 끝에 추가:

```python
def attach_facts_to_issues(
    issues: list[dict],
    scored: list[tuple[CollectedItem, int, str]],
    *,
    scope: str,
) -> list[dict]:
    """추출한 사실을 브리핑 픽에 종목코드/티커로 재결합한다.

    hot_issues 는 LLM 출력이라 CollectedItem 과의 링크가 끊긴다. 국내는 6자리
    종목코드, 해외는 extract_facts 가 스탬프한 티커로 맞춘다. 매칭 실패는 조용히
    건너뛴다 — 사실이 없다고 픽을 버릴 이유는 없다.
    """
    index: dict[str, dict] = {}
    for item, _s, _d in scored:
        facts = (item.extra or {}).get("facts")
        if not facts:
            continue
        key = (item.extra or {}).get("ticker") if scope == "foreign" else item.company_code
        if key:
            index[str(key).strip().upper()] = facts

    if not index:
        return issues

    for issue in issues:
        for pick in issue.get("picks") or []:
            facts = index.get(str(pick.get("ticker") or "").strip().upper())
            if facts:
                pick["facts"] = facts
    return issues
```

- [ ] **Step 3: 재결합 테스트 통과 확인 후 orchestrator 배선**

Run: `pytest tests/test_filing_pipeline.py -q`
Expected: PASS

`orchestrator.py` 의 import 에 `attach_facts_to_issues` 를 추가하고,
`_run_foreign()` / `_run_domestic()` 결과를 `pick_verify` 로 거른 **직후**, 브리핑 JSON 을
만들기 전에 부착한다:

```python
        hot_foreign = attach_facts_to_issues(hot_foreign, scored, scope="foreign")
        hot_domestic = attach_facts_to_issues(hot_domestic, scored, scope="domestic")
```

(변수명은 해당 위치의 실제 이름을 따른다. 브리핑 JSON 빌더에 넘어가는 issues 리스트여야 한다.)

- [ ] **Step 4: 원장 적재의 실패하는 테스트 작성**

`tests/test_picks_outcomes.py` 끝에 추가:

```python
def test_extract_outcome_rows_carries_facts_json():
    """픽에 붙은 facts 가 원장에 직렬화돼 임계값 재조정 근거로 남는다."""
    import json

    from news_briefing.analysis.picks_outcomes import extract_outcome_rows

    briefing = {
        "date": "2026-07-09",
        "tabs": {"economy": {"hotIssues": {"foreign": [{
            "asset": "반도체", "direction": "positive", "signal": "어닝 서프라이즈",
            "picks": [{
                "ticker": "AAPL", "name": "Apple",
                "facts": {"kind": "earnings", "surprise_pct": 6.34},
            }],
        }], "domestic": []}}},
    }

    rows = extract_outcome_rows(briefing)

    assert len(rows) == 1
    assert json.loads(rows[0]["facts_json"])["surprise_pct"] == 6.34


def test_extract_outcome_rows_facts_json_none_when_absent():
    from news_briefing.analysis.picks_outcomes import extract_outcome_rows

    briefing = {
        "date": "2026-07-09",
        "tabs": {"economy": {"hotIssues": {"foreign": [{
            "asset": "반도체", "direction": "positive", "signal": "x",
            "picks": [{"ticker": "AAPL", "name": "Apple"}],
        }], "domestic": []}}},
    }

    assert extract_outcome_rows(briefing)[0]["facts_json"] is None
```

- [ ] **Step 5: 테스트 실패 확인**

Run: `pytest tests/test_picks_outcomes.py -q -k facts_json`
Expected: FAIL — `KeyError: 'facts_json'`

- [ ] **Step 6: `extract_outcome_rows` 수정**

`src/news_briefing/analysis/picks_outcomes.py` 의 `rows.append({...})` 안,
`"is_filer": ...` 줄 바로 다음에 추가:

```python
                        "facts_json": (
                            json.dumps(pick["facts"], ensure_ascii=False)
                            if pick.get("facts")
                            else None
                        ),
```

파일 상단에 `import json` 이 없으면 추가한다.

- [ ] **Step 7: 스키마 갱신**

`scripts/supabase_schema.sql` 의 `pick_outcomes` 테이블 정의에 컬럼을 추가하고, 파일 끝에
기존 DB 용 마이그레이션을 덧붙인다:

```sql
-- 2026-07-09 공시 본문 분석: 추출한 사실을 원장에 남겨 임계값 재조정 근거로 쓴다
ALTER TABLE pick_outcomes ADD COLUMN IF NOT EXISTS facts_json TEXT;
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `pytest tests/test_picks_outcomes.py -q`
Expected: PASS (기존 + 신규 2개)

- [ ] **Step 9: 사용자 승인 후 마이그레이션 적용**

사용자에게 위 `ALTER TABLE` 실행 승인을 요청한다. 승인 시 Supabase MCP `apply_migration`
(project_id `lbipfgechqeknzrlxxpc`, name `add_facts_json_to_pick_outcomes`) 으로 적용한다.
**승인 없이 실행하지 않는다.**

- [ ] **Step 10: 린트 후 커밋**

```bash
ruff format src/news_briefing/analysis/picks_outcomes.py src/news_briefing/analysis/filing_facts.py tests/test_picks_outcomes.py
ruff check --fix src/news_briefing/ tests/
pytest -q
git add src/news_briefing/analysis/picks_outcomes.py src/news_briefing/analysis/filing_facts.py src/news_briefing/orchestrator.py scripts/supabase_schema.sql tests/test_picks_outcomes.py tests/test_filing_pipeline.py
git commit -m "feat(filing): 추출한 사실을 pick_outcomes.facts_json 에 적재

임계값(서프라이즈 ±5/±10%, YoY ±30%)은 관행 기반 초기값이다.
구간별 alpha 를 집계해 실측으로 옮기려면 사실이 원장에 남아야 한다."
```

---

### Task 7: 통합 검증 (dry-run)

**Files:**
- 없음 (실행 검증만)

- [ ] **Step 1: 실제 파이프라인 dry-run**

```bash
dotenvx run -- python -m news_briefing morning --dry-run
```

Expected: 로그에 `3-b. 공시 본문 분석` 소요시간과 `filing_analysis: 대상 N건, 재점수 M건` 이
찍힌다. 예외로 죽지 않는다.

- [ ] **Step 2: 재점수가 실제로 일어났는지 확인**

로그의 `재점수 M건` 이 `0` 이면 게이팅이 과했거나 분류가 안 맞는 것이다.
룩백 창에 실적 공시가 실제로 있는지 먼저 확인한다:

```bash
dotenvx run -- python -c "
import os
from news_briefing.collectors.dart import fetch_dart_list
from news_briefing.analysis.filing_facts import classify_filing
items = fetch_dart_list(os.environ['DART_API_KEY'], '20260701', end_date='20260709')
kinds = [classify_filing(i) for i in items]
print('전체', len(items), '실적', kinds.count('earnings'), '합병', kinds.count('merger'))
"
```

- [ ] **Step 3: 캐시 동작 확인**

같은 명령을 한 번 더 실행해 두 번째 실행에서 `3-b` 소요시간이 크게 줄어드는지 본다
(llm_cache 적중).

- [ ] **Step 4: 전체 테스트 + 커밋**

```bash
pytest
ruff check src/ tests/
git commit --allow-empty -m "chore(filing): 본문 분석 파이프라인 dry-run 검증 완료"
```

---

## 후속 (이 계획의 범위 밖)

- **C단계 해설**: `FilingFacts` 가 채워진 픽에 한해, 추출된 숫자만 근거로 한 문장 해석 생성.
  본문 원문을 프롬프트에 넣지 않아 그라운딩을 강제한다. 별도 명세로 진행.
- **임계값 실측 재조정**: `facts_json` 이 두어 달 쌓이면 `alpha_5d` 를 서프라이즈 구간별로
  갈라 실제 경계를 찾는다. 변경 시 사용자 승인 + `DECISIONS.md` 기록.
