"""LLM 기반 '오늘의 주목 종목/테마' 분석.

해외(foreign): EDGAR·FT·BBC 등 Tier 1 해외 소스 우선.
국내(domestic): DART 공시·증권사 리포트·한경·매경 소스 우선.
뉴스 나열 대신 투자 대상(종목·테마)을 먼저 제시하고 근거 기사를 함께 반환한다.
"""

from __future__ import annotations

import json
import logging
import time

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

# ── 해외용 소스 티어 ─────────────────────────────────────────────
_TIER_MAP_FOREIGN: dict[str, int] = {
    "edgar": 1,
    "rss:ft-markets": 1,
    "rss:bbc-business": 1,
    "rss:bbc-world": 1,
    "rss:gnews-world-en": 2,
    "rss:gnews-business-en": 2,
    "rss:gnews-tech-en": 2,
    "rss:gnews-us-stocks-en": 2,
    "rss:gnews-us-markets-en": 2,
    "rss:marketwatch": 2,
}

# ── 국내용 소스 티어 ─────────────────────────────────────────────
_TIER_MAP_DOMESTIC: dict[str, int] = {
    "dart": 1,  # DART 공시 최우선
    "research": 1,  # 증권사 리포트
    "rss:hankyung": 2,
    "rss:mk": 2,
    "rss:yonhap-kr": 2,
    "rss:yonhap-intl": 2,  # 연합뉴스 국제 — 국내 시사 Tier 2
    "rss:gnews-business-kr": 3,
    "rss:gnews-stock-kr": 3,
}

_DEFAULT_TIER = 3

# ── 표시용 언론사명 ──────────────────────────────────────────────
_DISPLAY_MAP: dict[str, str] = {
    "edgar": "SEC EDGAR",
    "dart": "DART",
    "research": "증권사 리포트",
    "rss:ft-markets": "Financial Times",
    "rss:bbc-business": "BBC Business",
    "rss:bbc-world": "BBC World",
    "rss:gnews-world-en": "Google News (World)",
    "rss:gnews-business-en": "Google News (Business)",
    "rss:gnews-tech-en": "Google News (Tech)",
    "rss:yonhap-intl": "연합뉴스 국제",
    "rss:yonhap-kr": "연합뉴스",
    "rss:hankyung": "한국경제",
    "rss:mk": "매일경제",
    "rss:gnews-business-kr": "Google News (경제)",
    "rss:gnews-stock-kr": "Google News (증시)",
    "rss:gnews-us-stocks-en": "Google News (미국 증시)",
    "rss:gnews-us-markets-en": "Google News (미국 시장)",
    "rss:marketwatch": "MarketWatch",
}


def source_tier_foreign(source: str) -> int:
    return _TIER_MAP_FOREIGN.get(source, _DEFAULT_TIER)


def source_tier_domestic(source: str) -> int:
    return _TIER_MAP_DOMESTIC.get(source, _DEFAULT_TIER)


def source_display(source: str) -> str:
    return _DISPLAY_MAP.get(source, source)


def foreign_news_weight(source: str) -> int:
    """해외 뉴스(비공시) 소스의 신뢰도 기반 기본 점수.

    EDGAR·gov_contracts 같은 공시는 내용 기반 점수(45~95)를 따로 받으므로 이 함수 대상이 아니다.
    뉴스에는 '내용 점수'가 없어 소스 신뢰도를 점수로 환산한다.
    curation_score(시간 감쇠) 대신 사용 — 방금 올라온 기사가 신뢰도 높은 소스를
    제치고 picks 상위를 차지하던 문제를 막는다.

    - Tier 1 (FT·BBC): 65 — EDGAR 평균(70)보다 살짝 아래
    - Tier 2 (MarketWatch·Google News 영문): 50
    - 그 외: 42 (score_floor 40 바로 위 — EDGAR 없는 날 fallback으로만 생존)
    """
    return {1: 65, 2: 50}.get(source_tier_foreign(source), 42)


_PROMPT_SYSTEM = """\
너는 해외 주식 투자자를 위한 투자 리서치 에디터다.
아래 오늘 수집된 기사·공시 목록을 분석해, 오늘 당장 주목해야 할 종목·테마·자산 3개를 선정하라.

핵심 원칙:
- 뉴스 자체가 아니라 **투자 대상(종목·테마·자산)**을 먼저 제시한다
- 기사·공시는 그 주장의 근거로만 사용한다
- Tier 1 소스(SEC EDGAR·Financial Times·BBC)를 우선 참고한다
- 미국·글로벌 투자자 관점 (한국 내수 테마 제외)
- 기업명·제품명·브랜드명 등 고유명사는 원문(영문) 그대로 표기한다. 음역 절대 금지 (예: Anthropic → Anthropic, 앤스로픽 X)

선정 기준 (우선순위):
1. SEC EDGAR 8-K 공시: 기업 실적·가이던스·M&A·구조조정 직접 공시
2. 중앙은행·정부 정책 발표: 금리·규제·무역 정책이 특정 섹터/자산에 미치는 영향
3. FT·BBC 단독 보도: 시장 가격에 아직 반영 안 된 새로운 정보

주목도 사이클 우선순위 (★ 핵심 — 개미보다 빠른 진입이 목표):
- [P1] 초기 진입 구간: 첫 시그널, 가격 미반영 → 최우선 선정
- [P2] 상승 초반: 주목도 가속 중, 일부 반영 → 선정 가능
- [P3] 주류: 언론 도배·이미 상승 → 후순위 (불가피한 경우만)
- [P4] 고점 경계: 주목도 꺾임·고점권 → 선정 금지
항목 옆 [P숫자] 태그를 참고해 P1·P2 위주로 선정하라.
4. 매크로 변화: 달러·금리·원자재 흐름이 특정 ETF·섹터로 직결

picks 작성 원칙 (★ 핵심 — 가장 중요):
목표: 개미 투자자 대다수가 아직 연결고리를 파악하지 못한 종목을 찾는 것.
"가장 유명한 수혜주"가 아니라 "아직 덜 알려진 파생 수혜주"를 골라라.

필수 사고 순서:
1. 이 이슈와 picks 후보 사이의 연결고리가 이미 시장에서 "당연한 것"으로 인식되는지 판단한다.
   - 연결고리가 뻔하면 → consensus_risk="high", 제외
   - 연결고리가 아직 잘 알려지지 않았다면 → 유명 대기업이라도 포함 가능
2. 가능하면 2nd·3rd order 파생 수혜 종목을 우선 탐색한다.
   예: 방산 수주 급증 → 방산 부품·소재사 / AI 수요 급증 → 냉각 시스템·전력 인프라주
3. 선정한 picks 각각에 대해 "consensus_risk"를 스스로 평가한다.
   - "high": 해당 이슈-종목 연결고리가 이미 언론 도배·애널 다수 커버·주가 선반영 → 제외
   - "medium": 일부 언급 있으나 아직 주류 아님 → 허용
   - "low": 거의 언급 없음, 시장이 아직 연결고리를 못 봄 → 최우선

- consensus_risk="high" 종목은 picks 배열에 포함 금지
- picks는 이슈 자체가 아닌 파생 투자 대상. 이슈와 picks가 같아선 안 됨
- 국내 추종 ETF: ISA·연금 계좌에서 매수 가능한 국내 ETF를 반드시 병기. 없으면 null

출력 규칙:
- JSON 배열만 반환. 마크다운 코드블록·설명 텍스트 없이 배열 그대로.
- 배열 길이 정확히 3.
- 각 원소:
  {
    "rank": 숫자,
    "asset": "이슈 대상 이름. 종목이면 티커(예: NVDA), 테마면 짧은 한국어(예: 에너지·반도체), 매크로면 자산명(예: WTI원유). 절대 뉴스 제목을 쓰지 말 것.",
    "assetType": "stock" | "theme" | "macro",
    "direction": "positive" | "negative" | "mixed",
    "signal": "핵심 시그널 15자 이내 (예: 가이던스 상향, 금리 동결, 규제 리스크)",
    "reason": "왜 오늘 이 자산에 주목해야 하는지 2~3문장, 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓), 구체적 수치 포함",
    "cautions": "이 thesis가 뒤집힐 수 있는 핵심 리스크 1~2문장, 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓). 리스크가 없으면 null.",
    "picks": [
      {
        "ticker": "미국 심볼 (예: JETS, DAL, XLY)",
        "name": "한국어 기업·펀드명 (예: 미국항공 ETF, 델타항공, 소비재 ETF)",
        "description": "이 종목을 추천하는 이유와 수혜 메커니즘 1~2문장, 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓)",
        "why_undiscovered": "왜 아직 시장이 이 연결고리를 파악하지 못했는지 1문장",
        "consensus_risk": "low" | "medium",
        "related_etf": 이 종목을 많이 담은 해외(미국 상장) ETF 1개 또는 null (규칙 아래 참고),
        "domestic": 국내 ISA·연금계좌용 ETF 배열 또는 null (규칙 아래 참고)
      }
    ],
    "source": "출처 언론사명",
    "url": "원문 URL 또는 null"
  }
  picks 배열은 2~3개. consensus_risk="high"는 포함 금지.

related_etf 필드 작성 규칙 (★ 필수, domestic과 별개):
- 의미: 이 종목을 비중 있게 보유한 **해외(미국 상장) ETF** 1개. (domestic은 국내 추종 ETF로 별개 필드)
- 형식: {"ticker": "ETF심볼", "name": "ETF명"} 또는 null (배열 아님, 단일 객체)
- 선택 기준: 동일 종목·테마를 담은 ETF가 운용사별로 여러 개면, **거래량 많고 대중적이며 운용보수(expense ratio)가 가장 낮은** 1개를 고른다 (예: 반도체 → SMH 또는 SOXX, S&P500 → VOO/IVV, 빅테크 → QQQ).
- 해당 종목을 직접 담은 ETF가 없으면 동일 섹터·테마 대표 ETF로 대체. 그래도 없으면 null.
- 심볼이 불확실하면 {"ticker": "", "name": "ETF명"} 형태로 이름만 반환.

domestic 필드 작성 규칙 (★ 필수):
- 형식: [{"ticker": "ETF코드", "name": "ETF명"}, ...] 또는 null
- 단일 객체가 아닌 **배열**로 반환 (1개여도 배열)
- 탐색 순서 — 아래 순서로 찾고, 하나라도 찾으면 반환:
  1. 해당 종목·지수를 직접 추종하는 국내 ETF (TIGER·KODEX·KBSTAR·ACE·HANARO 계열)
  2. 해당 종목이 상위 보유종목으로 포함된 국내 ETF (예: AFL → TIGER 미국다우존스30)
  3. 동일 섹터·테마를 추종하는 국내 ETF (예: 방산株 → KODEX 미국방산항공우주, 채권 ETF → TIGER 미국단기채권)
  4. 유사 테마 ETF (예: 보험株 → TIGER 미국금융 또는 KODEX 미국S&P500금융)
- null은 위 4단계를 모두 탐색해도 국내 상장 ETF가 전혀 없을 때만 사용
- 코드(ticker)가 불확실하면 코드 없이 {"ticker": "", "name": "ETF명"} 형태로 이름만 반환
- 개별 종목(single stock)도 반드시 해당 섹터 ETF를 탐색해 반환할 것 (null 금지 원칙)
"""

_PROMPT_SYSTEM_DOMESTIC = """\
너는 코스피·코스닥 투자자를 위한 국내 주식 리서치 에디터다.
아래 오늘 수집된 DART 공시·증권사 리포트·국내 경제 뉴스를 분석해,
오늘 당장 주목해야 할 국내 종목·테마 3개를 선정하라.

핵심 원칙:
- 코스피·코스닥 투자자 관점 (해외 종목 제외)
- DART 공시 최우선 (실적·가이던스·M&A·자사주·유무상증자 직접 공시)
- 증권사 목표주가 상향/신규 커버리지도 중요한 시그널
- 한국 내수·수출·산업 테마 포함 가능
- 기업명·제품명·브랜드명 등 고유명사는 원문(영문) 그대로 표기한다. 음역 절대 금지 (예: Anthropic → Anthropic, 앤스로픽 X)

선정 기준 (우선순위):
1. DART 공시: 어닝 서프라이즈·가이던스 상향·M&A·자사주 매입 등 직접 촉매
2. 증권사 리포트: 목표주가 상향(10% 이상) 또는 신규 커버리지 개시
3. 국내 경제 뉴스: 정부 정책·규제 변화가 특정 섹터에 미치는 영향
4. 테마 시그널: 동일 섹터 내 복수 기업에 영향을 주는 구조적 변화

주목도 사이클 우선순위 (★ 핵심 — 개미보다 빠른 진입이 목표):
- [P1] 초기 진입 구간: 첫 시그널, 가격 미반영 → 최우선 선정
- [P2] 상승 초반: 주목도 가속 중, 일부 반영 → 선정 가능
- [P3] 주류: 언론 도배·이미 상승 → 후순위 (불가피한 경우만)
- [P4] 고점 경계: 주목도 꺾임·고점권 → 선정 금지
항목 옆 [P숫자] 태그를 참고해 P1·P2 위주로 선정하라.

picks 작성 원칙 (★ 핵심 — 가장 중요):
목표: 개미 투자자 대다수가 아직 연결고리를 파악하지 못한 국내 종목을 찾는 것.

필수 사고 순서:
1. 이 이슈와 picks 후보 사이의 연결고리가 이미 시장에서 "당연한 것"으로 인식되는지 판단한다.
   - 연결고리가 뻔하면 → consensus_risk="high", 제외
   - 연결고리가 아직 잘 알려지지 않았다면 → 대형주라도 포함 가능
2. 가능하면 2nd·3rd order 파생 수혜 종목을 우선 탐색한다.
   예: 방산 수주 급증 → 방산 부품·소재 중소기업 / AI 인프라 → 서버 부품·PCB·냉각재 기업
3. picks 각각에 대해 consensus_risk를 평가한다.
   - "high": 해당 이슈-종목 연결고리가 이미 언론 도배·증권사 다수 커버·주가 선반영 → 제외
   - "medium": 일부 언급 있으나 아직 주류 아님 → 허용
   - "low": 거의 미발굴, 시장이 연결고리를 아직 못 봄 → 최우선

- consensus_risk="high" 종목은 picks 배열에 포함 금지
- ticker는 한국 종목코드(6자리 숫자, 예: 005930) 또는 ETF 코드
- related_etf: 이 종목을 비중 있게 담은 국내 상장 ETF 1개를 병기 (규칙 아래 참고)
- domestic 필드는 반드시 null (picks 자체가 국내 종목)
- direction=negative이면 수혜받는 국내 종목을 picks로 제시

출력 규칙:
- JSON 배열만 반환. 마크다운 코드블록·설명 텍스트 없이 배열 그대로.
- 배열 길이 정확히 3.
- 각 원소:
  {
    "rank": 숫자,
    "asset": "이슈 대상. 종목이면 기업명(예: 삼성전자), 테마면 짧은 한국어(예: 2차전지·방산), 매크로면 자산명. 절대 뉴스 제목을 쓰지 말 것.",
    "assetType": "stock" | "theme" | "macro",
    "direction": "positive" | "negative" | "mixed",
    "signal": "핵심 시그널 15자 이내 (예: 목표주가 상향, 어닝 서프라이즈, 자사주 매입)",
    "reason": "왜 오늘 이 자산에 주목해야 하는지 2~3문장, 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓), 구체적 수치 포함",
    "cautions": "이 thesis가 뒤집힐 수 있는 핵심 리스크 1~2문장, 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓). 리스크가 없으면 null.",
    "picks": [
      {
        "ticker": "한국 종목코드 6자리 (예: 005930)",
        "name": "기업명 또는 ETF명",
        "description": "이 종목을 추천하는 이유와 수혜 메커니즘 1~2문장, 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓)",
        "why_undiscovered": "왜 아직 시장이 이 연결고리를 파악하지 못했는지 1문장",
        "consensus_risk": "low" | "medium",
        "related_etf": 이 종목을 많이 담은 국내 상장 ETF 1개 또는 null (규칙 아래 참고),
        "domestic": null
      }
    ],
    "source": "출처 언론사·기관명",
    "url": "원문 URL 또는 null"
  }
  picks 배열은 2~3개. domestic은 항상 null.

related_etf 필드 작성 규칙 (★ 필수):
- 의미: 이 국내 종목을 비중 있게 담은 **국내 상장 ETF** 1개 (TIGER·KODEX·KBSTAR·ACE·HANARO 계열).
- 형식: {"ticker": "ETF코드", "name": "ETF명"} 또는 null (배열 아님, 단일 객체)
- 선택 기준: 동일 종목·테마를 담은 ETF가 운용사별로 여러 개면, **순자산·거래량 많고 대중적이며 운용보수가 가장 낮은** 1개를 고른다.
- 해당 종목을 직접 담은 ETF가 없으면 동일 섹터·테마 대표 ETF로 대체. 그래도 없으면 null.
- 코드가 불확실하면 {"ticker": "", "name": "ETF명"} 형태로 이름만 반환.
"""


def _parse_issues(raw: str) -> list[dict]:
    """LLM 출력 → 검증된 HotIssue 리스트. 공통 파싱 로직."""
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[:-1])
    raw = raw.strip()

    issues: list[dict] = json.loads(raw)
    validated: list[dict] = []
    for iss in issues[:3]:
        asset = str(iss.get("asset") or iss.get("title") or "").strip()
        if not asset:
            continue
        raw_picks = iss.get("picks") or []
        picks: list[dict] = []
        for p in raw_picks[:3]:
            if not isinstance(p, dict):
                continue
            ticker = str(p.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            domestic_raw = p.get("domestic")
            domestic = None
            if isinstance(domestic_raw, dict):
                d_ticker = str(domestic_raw.get("ticker") or "").strip()
                d_name = str(domestic_raw.get("name") or "").strip()
                if d_ticker and d_name:
                    domestic = {"ticker": d_ticker, "name": d_name}
            related_raw = p.get("related_etf")
            related = None
            if isinstance(related_raw, dict):
                r_ticker = str(related_raw.get("ticker") or "").strip()
                r_name = str(related_raw.get("name") or "").strip()
                if r_name:  # 이름만 있어도 채택 (코드 불확실 허용)
                    related = {"ticker": r_ticker, "name": r_name}
            picks.append(
                {
                    "ticker": ticker,
                    "name": str(p.get("name") or "").strip(),
                    "description": str(p.get("description") or "").strip(),
                    "why_undiscovered": str(p.get("why_undiscovered") or "").strip() or None,
                    "consensus_risk": str(p.get("consensus_risk") or "medium").strip(),
                    "related_etf": related,
                    "domestic": domestic,
                }
            )
        cautions_raw = iss.get("cautions")
        cautions = str(cautions_raw).strip() if cautions_raw and str(cautions_raw).strip() else None

        entry: dict = {
            "rank": int(iss.get("rank", len(validated) + 1)),
            "asset": asset,
            "assetType": iss.get("assetType") or "theme",
            "direction": iss.get("direction") or "mixed",
            "signal": str(iss.get("signal") or "").strip(),
            "picks": picks,
            "reason": str(iss.get("reason") or "").strip(),
            "source": str(iss.get("source") or "").strip(),
            "url": iss.get("url") or None,
        }
        if cautions:
            entry["cautions"] = cautions
        validated.append(entry)
    return validated


def _build_pool(
    candidates: list[tuple[CollectedItem, int]],
    tier_fn,
    *,
    tier1_cap: int | None = None,  # None = 무제한
    tier2_cap: int = 8,
    tier3_cap: int = 3,
    score_floor: int = 40,
) -> list[tuple[CollectedItem, int, int]]:
    """Tier별 쿼터 + 동일 기업 중복 제거 + 점수 하한 필터링.

    - Tier 1 (공시·핵심 소스): cap 없음 — 어떤 날이든 전부 포함
    - Tier 2 (주요 언론): 최대 tier2_cap개, 기업 중복 제거
    - Tier 3 (Google News 등): 최대 tier3_cap개, Tier 1+2 풀이 부족할 때만
    - score_floor 미만은 노이즈로 간주해 제외
    """
    # 1. 점수 하한 + Tier 계산
    tagged = [
        (item, score, tier_fn(item.source)) for item, score in candidates if score >= score_floor
    ]
    tagged.sort(key=lambda x: (x[2], -x[1]))

    seen_companies: set[str] = set()
    tier_counts = {1: 0, 2: 0, 3: 0}
    pool: list[tuple[CollectedItem, int, int]] = []

    for item, score, tier in tagged:
        cap = {1: tier1_cap, 2: tier2_cap, 3: tier3_cap}.get(tier, tier3_cap)
        if cap is not None and tier_counts[tier] >= cap:
            continue
        # Tier 2·3 은 동일 기업 중복 제거 (Tier 1 공시는 같은 기업 공시 여러 개도 의미 있음)
        company_key = (item.company or item.title[:30]).strip().lower()
        if tier >= 2 and company_key in seen_companies:
            continue
        seen_companies.add(company_key)
        tier_counts[tier] += 1
        pool.append((item, score, tier))

    return pool


def _pool_to_prompt_lines(
    pool: list[tuple[CollectedItem, int, int]],
    phase_map: dict[str, int] | None = None,
) -> list[str]:
    """모든 Tier URL 포함. phase_map 있으면 [P숫자] 태그 추가."""
    lines = []
    for idx, (item, score, tier) in enumerate(pool, 1):
        display = source_display(item.source)
        phase = (phase_map or {}).get(item.ext_id)
        phase_tag = f"[P{phase}] " if phase else ""
        # 기업명이 있으면 제목 앞에 붙여 LLM이 분석할 수 있도록 함
        company_part = f"{item.company} · " if item.company else ""
        url_part = f" | {item.url}" if item.url else ""
        lines.append(f"{idx}. {phase_tag}[{display}] {company_part}{item.title}{url_part}")
    return lines


def analyze_hot_issues(
    candidates: list[tuple[CollectedItem, int]],
    *,
    phase_map: dict[str, int] | None = None,
) -> list[dict]:
    """해외 소스 기반 오늘 주목할 종목·테마 Top 3 선정.

    Tier 1 (EDGAR·FT·BBC): 전량 포함.
    Tier 2 (Google News·연합 국제): 기업 중복 제거 후 최대 8개.
    Tier 3: 최대 3개.
    phase_map: {ext_id: phase} — 있으면 각 항목에 [P숫자] 태그 추가해 LLM이 P1·P2 우선 선정.
    실패 시 빈 리스트 반환.
    """
    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    pool = _build_pool(candidates, source_tier_foreign, tier1_cap=10, tier2_cap=8, tier3_cap=3)

    if not pool:
        log.warning("hot_issues(foreign): 후보 아이템 없음, 분석 건너뜀")
        return []

    lines = _pool_to_prompt_lines(pool, phase_map)
    prompt = _PROMPT_SYSTEM + "\n\n---\n\n" + "\n".join(lines)
    log.info(
        "hot_issues(foreign): 프롬프트 %d개 항목 (Tier1=%d Tier2=%d Tier3=%d)",
        len(pool),
        sum(1 for *_, t in pool if t == 1),
        sum(1 for *_, t in pool if t == 2),
        sum(1 for *_, t in pool if t == 3),
    )

    try:
        raw = _call_claude(prompt, timeout=300).strip()
        result = _parse_issues(raw)
        log.info("hot_issues(foreign): %d개 이슈 선정", len(result))
        return result
    except Exception as e:
        log.error("hot_issues(foreign) LLM 분석 실패: %s", e)
        return []


def analyze_hot_issues_domestic(
    candidates: list[tuple[CollectedItem, int]],
    *,
    phase_map: dict[str, int] | None = None,
) -> list[dict]:
    """국내 소스(DART·리서치·한경·매경) 기반 오늘 주목할 종목·테마 Top 3 선정.

    Tier 1 (DART·리서치): 실질 촉매 공시만 (score≥75: 실적·M&A·자사주·공급계약 등).
    Tier 2 (한경·매경·연합): 기업 중복 제거 후 최대 8개.
    Tier 3 (Google News): 최대 3개.
    phase_map: {ext_id: phase} — 있으면 각 항목에 [P숫자] 태그 추가해 LLM이 P1·P2 우선 선정.
    실패 시 빈 리스트 반환.
    """
    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    pool = _build_pool(
        candidates, source_tier_domestic, tier1_cap=15, tier2_cap=8, tier3_cap=3, score_floor=75
    )

    if not pool:
        log.warning("hot_issues(domestic): 후보 아이템 없음, 분석 건너뜀")
        return []

    lines = _pool_to_prompt_lines(pool, phase_map)
    prompt = _PROMPT_SYSTEM_DOMESTIC + "\n\n---\n\n" + "\n".join(lines)
    log.info(
        "hot_issues(domestic): 프롬프트 %d개 항목 (Tier1=%d Tier2=%d Tier3=%d)",
        len(pool),
        sum(1 for *_, t in pool if t == 1),
        sum(1 for *_, t in pool if t == 2),
        sum(1 for *_, t in pool if t == 3),
    )

    for attempt in range(2):
        try:
            raw = _call_claude(prompt, timeout=300).strip()
            result = _parse_issues(raw)
            log.info("hot_issues(domestic): %d개 이슈 선정", len(result))
            return result
        except Exception as e:
            if attempt == 0:
                log.warning("hot_issues(domestic) 1차 실패, 30초 후 재시도: %s", e)
                time.sleep(30)
            else:
                log.error("hot_issues(domestic) LLM 분석 최종 실패: %s", e)
    return []
