"""추천 종목 사실 검증 — 2차 LLM 검증 + 티커 실존 확인.

hot_issues 가 생성한 picks 를 build_briefing_json 전에 한 번 더 거른다.

1. 2차 LLM 검증: 각 pick 의 종목↔테마 연결고리를 근거 소스와 대조해
   환각(존재하지 않는 연결·날조 티커)을 'drop' 으로 솎아낸다.
2. 티커 실존 확인: 해외는 yfinance, 국내는 tickers DB + yfinance 로 심볼이
   실제 거래되는지 확인. 확인 실패는 drop 이 아니라 'review' 플래그(네트워크
   일시 장애로 정상 종목을 잃지 않도록).

각 pick 에 verifyStatus("ok"|"review") 를 스탬프한다. 어떤 단계가 실패해도
원본 picks 를 보존해 파이프라인을 멈추지 않는다.
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger(__name__)

_DOMESTIC_CODE_RE = re.compile(r"^\d{6}$")


# ── 티커 실존 확인 ────────────────────────────────────────────────
def verify_ticker_exists(ticker: str, scope: str, conn=None) -> bool:
    """심볼이 실제 거래되는 종목인지 확인. 확인 가능하면 True, 아니면 False.

    False 는 '확정 부재'가 아니라 '확인 불가'까지 포함 — 호출부에서 drop 이 아니라
    review 플래그로만 처리한다.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return False

    if scope == "domestic":
        # 1) 6자리 코드 형식이 아니면 의심
        if not _DOMESTIC_CODE_RE.match(ticker):
            return False
        # 2) tickers DB 매핑 우선 (DART 수집 시 누적)
        if conn is not None:
            try:
                from news_briefing.storage.tickers import get_ticker_by_stock

                if get_ticker_by_stock(conn, ticker) is not None:
                    return True
            except Exception as e:
                log.debug("tickers DB 조회 실패(%s): %s", ticker, e)
        # 3) yfinance .KS/.KQ fallback
        return _yf_exists([f"{ticker}.KS", f"{ticker}.KQ"])

    # foreign
    return _yf_exists([ticker])


def _yf_exists(candidates: list[str]) -> bool:
    """yfinance 로 후보 심볼 중 하나라도 최근 거래내역이 있으면 True."""
    try:
        import yfinance as yf
    except Exception:
        return False
    for sym in candidates:
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if hist is not None and not hist.empty:
                return True
        except Exception:
            continue
    return False


# ── 2차 LLM 검증 ──────────────────────────────────────────────────
_VERIFY_PROMPT = """\
너는 투자 리서치 팩트체커다. 아래 '추천 종목' 목록의 각 종목이 제시된 테마·근거와
실제로 연결되는지, 그리고 티커가 실존하는 종목인지 비판적으로 검증한다.

판정 규칙:
- "drop": 종목↔테마 연결이 사실과 다르거나 근거가 전혀 없음, 또는 날조된 것으로 보이는 티커·기업명
- "flag": 연결은 그럴듯하나 근거가 약하거나 확인이 더 필요함
- "keep": 근거가 충분하고 연결이 타당함

엄격하게 판단하되, 합리적 수혜 연결고리(2·3차 파생 포함)는 keep 으로 인정한다.

출력 규칙:
- JSON 배열만 반환. 마크다운·설명 없이 배열 그대로.
- 각 원소: {"ticker": "심볼", "verdict": "keep"|"flag"|"drop", "reason": "한 문장"}
- 입력에 있는 모든 ticker 를 빠짐없이 포함한다.
"""


def _picks_to_lines(issues: list[dict]) -> list[str]:
    lines: list[str] = []
    for iss in issues:
        asset = iss.get("asset", "")
        signal = iss.get("signal", "")
        for p in iss.get("picks") or []:
            lines.append(
                f"- ticker={p.get('ticker', '')} | name={p.get('name', '')} | "
                f"테마={asset} ({signal}) | 근거={p.get('description', '')} "
                f"| why_undiscovered={p.get('why_undiscovered') or ''}"
            )
    return lines


def verify_picks_llm(issues: list[dict], evidence_lines: list[str]) -> dict[str, str]:
    """각 pick 티커 → 'keep'|'flag'|'drop' 판정. 실패 시 빈 dict(=모두 keep 취급)."""
    pick_lines = _picks_to_lines(issues)
    if not pick_lines:
        return {}

    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    evidence = "\n".join(f"  {ln}" for ln in evidence_lines[:60]) or "  (근거 소스 없음)"
    prompt = (
        _VERIFY_PROMPT
        + "\n\n## 추천 종목\n"
        + "\n".join(pick_lines)
        + "\n\n## 근거 소스(오늘 수집)\n"
        + evidence
    )

    try:
        raw = _call_claude(prompt, timeout=180, model="sonnet").strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.splitlines()[:-1])
        raw = raw.strip()
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if not m:
                raise
            rows = json.loads(m.group(0))
    except Exception as e:
        log.warning("pick_verify LLM 실패 (모두 keep 처리): %s", e)
        return {}

    verdicts: dict[str, str] = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        t = str(r.get("ticker") or "").strip().upper()
        v = str(r.get("verdict") or "keep").strip().lower()
        if t and v in ("keep", "flag", "drop"):
            verdicts[t] = v
    return verdicts


# ── 통합 적용 ─────────────────────────────────────────────────────
def apply_verification(
    issues: list[dict],
    *,
    scope: str,
    conn=None,
    evidence_lines: list[str] | None = None,
) -> list[dict]:
    """issues 의 picks 를 검증해 환각 제거 + verifyStatus 스탬프.

    - LLM 판정 'drop' → 해당 pick 제거
    - LLM 판정 'flag' → verifyStatus='review'
    - 티커 실존 미확인 → verifyStatus='review' (제거하지 않음)
    - 그 외 → verifyStatus='ok'
    이슈의 picks 가 전부 제거돼도 이슈 자체는 빈 picks 로 유지한다.
    """
    verdicts = verify_picks_llm(issues, evidence_lines or [])

    dropped = 0
    flagged = 0
    for iss in issues:
        kept: list[dict] = []
        for p in iss.get("picks") or []:
            ticker = str(p.get("ticker") or "").strip().upper()
            verdict = verdicts.get(ticker, "keep")
            if verdict == "drop":
                dropped += 1
                continue
            exists = verify_ticker_exists(ticker, scope, conn)
            if verdict == "flag" or not exists:
                p["verifyStatus"] = "review"
                flagged += 1
            else:
                p["verifyStatus"] = "ok"
            kept.append(p)
        iss["picks"] = kept

    log.info("pick_verify(%s): drop %d, review %d", scope, dropped, flagged)
    return issues
