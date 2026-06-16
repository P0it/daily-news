"""추천 종목 사실 검증 — 2차 LLM 검증 + 티커 실존 확인.

hot_issues 가 생성한 picks 를 build_briefing_json 전에 한 번 더 거른다.

1. 2차 LLM 검증(이슈 단위 촉매 그라운딩): 각 이슈의 촉매(signal)가 근거 공시에
   실제로 존재하는지 먼저 확인해 날조 촉매는 이슈째 drop, 그 다음 각 pick 의
   종목↔촉매 연결·공시 주체(filer)를 대조해 환각 연결을 솎아낸다.
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


# 티커 형식·실존 판정 결과
#   "ok"        — 형식 정상 (실존은 미확인이거나 확인됨) → 플래그하지 않음
#   "malformed" — 형식 자체가 잘못됨(빈 값·국내 비6자리) → review 플래그
#
# 주의: FMP 무료 티어 quote-short 는 미커버 심볼에 'Premium' 에러를 주고,
# yfinance 는 정상 종목도 자주 실패한다. 둘 다 '없는 티커'와 '확인 불가'를
# 구분하지 못하므로, 확인 실패를 근거로 플래그하면 정상 종목 오탐이 쏟아진다.
# 따라서 실존 '양성 확인'은 신뢰도 보강용으로만 쓰고, 미확인은 ok 로 둔다.
# 환각·날조 티커 탐지는 2차 LLM 검증(verify_issues_llm)이 담당한다.
def verify_ticker_format(ticker: str, scope: str) -> str:
    """티커 형식 검증. 'ok' | 'malformed'."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return "malformed"
    if scope == "domestic" and not _DOMESTIC_CODE_RE.match(ticker):
        # 국내인데 6자리 숫자 코드가 아니면 LLM 이 잘못 만든 것
        return "malformed"
    return "ok"


def confirm_ticker_exists(ticker: str, scope: str, conn=None, fmp_api_key: str = "") -> bool:
    """가용한 소스로 실존을 '양성 확인'한다 (확인되면 True, 불확실하면 False).

    False 는 '없음'이 아니라 '확인 불가'를 포함 — 플래그 근거로 쓰지 않는다.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return False

    if scope == "domestic":
        if conn is not None:
            try:
                from news_briefing.storage.tickers import get_ticker_by_stock

                if get_ticker_by_stock(conn, ticker) is not None:
                    return True
            except Exception as e:
                log.debug("tickers DB 조회 실패(%s): %s", ticker, e)
        return _yf_exists([f"{ticker}.KS", f"{ticker}.KQ"])

    # foreign: FMP stable quote-short(권위) → 실패 시 yfinance
    if fmp_api_key and _fmp_exists(ticker, fmp_api_key):
        return True
    return _yf_exists([ticker])


def _fmp_exists(symbol: str, api_key: str) -> bool:
    """FMP stable quote-short 로 양성 확인. 데이터 배열이 오면 True, 그 외 False."""
    import requests

    try:
        resp = requests.get(
            "https://financialmodelingprep.com/stable/quote-short",
            params={"symbol": symbol, "apikey": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        return isinstance(data, list) and len(data) > 0 and bool(data[0].get("symbol"))
    except Exception:
        return False


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


# ── 2차 LLM 검증 (이슈 단위 촉매 그라운딩) ─────────────────────────
# 핵심: '픽↔테마' 연결만 보면 환각을 못 잡는다. 비에이치↔폴더블처럼 연결 자체는
# 사실이라 통과하지만, 정작 '최대주주 변경'이라는 촉매(사건)가 날조일 수 있다.
# 그래서 이슈마다 (1) 촉매 공시가 근거 목록에 실제로 존재하는지(grounded),
# (2) 그 공시 주체가 누구인지(filer)를 먼저 검증하고, 날조 촉매는 이슈째 drop 한다.
_VERIFY_PROMPT = """\
너는 투자 리서치 팩트체커다. 아래 '추천 이슈' 각각을 '근거 공시 목록'과 대조해
두 가지를 검증한다.

(1) 촉매 그라운딩 — 이슈의 '촉매(signal)'가 근거 공시 목록에 실제로 존재하는 사건인가:
    - grounded=true  : 그 사건 공시가 목록에 있음.
      filer=공시를 낸 회사명, evidence=해당 라인 1개를 그대로 인용.
    - grounded=false : 그 사건 공시가 목록 어디에도 없음(촉매 자체가 날조).
    주의: '테마가 그럴듯한지'가 아니라 '그 사건 공시가 목록에 실재하는지'만 본다.
    회사명 표기 차이(예: HD현대케미칼 = 에이치디현대케미칼)는 같은 회사로 본다.

(2) 픽 판정 — 각 추천 종목에 대해:
    - is_filer : 그 종목이 촉매 공시를 직접 낸 주체인가.
    - verdict:
      · "drop" = grounded=false 이거나, 종목↔촉매 연결이 사실과 다름·날조 티커.
      · "flag" = 촉매는 실재하나 (a) 공시 주체가 아닌 수혜주 추론인데 연결 근거가 약함,
                 또는 (b) 촉매 공시 주체가 다른 회사인데 이 종목으로 귀속됨(오귀속 의심).
      · "keep" = 공시 주체 본인이거나, 촉매가 실재하고 수혜 연결고리가 명확한 2·3차 수혜주.

출력 규칙:
- JSON 객체만 반환. 마크다운·설명 없이.
- 형식: {"issues":[{"idx":0,"grounded":true,"filer":"회사명 또는 null","evidence":"인용 또는 null",
  "picks":[{"ticker":"심볼","is_filer":true,"verdict":"keep|flag|drop","reason":"한 문장"}]}]}
- 입력의 모든 idx, 모든 ticker 를 빠짐없이 포함한다.
"""


def _issues_to_block(issues: list[dict]) -> str:
    """추천 이슈를 idx·촉매·픽 단위로 직렬화."""
    blocks: list[str] = []
    for idx, iss in enumerate(issues):
        asset = iss.get("asset", "")
        signal = iss.get("signal", "")
        head = f"[{idx}] 테마={asset} | 촉매={signal}"
        pick_lines = [
            f"    - ticker={p.get('ticker', '')} name={p.get('name', '')} "
            f"근거={p.get('description', '')}"
            for p in iss.get("picks") or []
        ]
        blocks.append("\n".join([head, *pick_lines]))
    return "\n".join(blocks)


def verify_issues_llm(
    issues: list[dict], evidence_lines: list[str]
) -> tuple[dict[int, dict], dict[tuple[int, str], dict]]:
    """이슈 단위 촉매 그라운딩 + 픽 판정.

    반환: (grounding, verdicts)
      - grounding[idx] = {"grounded": bool, "filer": str|None, "evidence": str|None}
      - verdicts[(idx, ticker)] = {"verdict": "keep"|"flag"|"drop", "reason": str, "is_filer": bool}
    실패 시 (빈 dict, 빈 dict) — 호출부가 모두 keep 으로 안전 처리(fail-open).
    """
    if not any(iss.get("picks") for iss in issues):
        return {}, {}

    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    # 근거는 점수순으로 정렬돼 들어온다는 전제(호출부 보장). 생성기가 본 고득점
    # 공시가 잘려나가 'grounded=false' 오탐이 나던 문제를 막으려 상한을 키운다.
    evidence = "\n".join(f"  {ln}" for ln in evidence_lines[:120]) or "  (근거 소스 없음)"
    prompt = (
        _VERIFY_PROMPT
        + "\n\n## 추천 이슈\n"
        + _issues_to_block(issues)
        + "\n\n## 근거 공시 목록(오늘 수집, 점수순)\n"
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
            obj = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                raise
            obj = json.loads(m.group(0))
    except Exception as e:
        log.warning("pick_verify LLM 실패 (모두 keep 처리): %s", e)
        return {}, {}

    grounding: dict[int, dict] = {}
    verdicts: dict[tuple[int, str], dict] = {}
    rows = obj.get("issues", []) if isinstance(obj, dict) else []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        try:
            idx = int(r.get("idx"))
        except (TypeError, ValueError):
            continue
        grounding[idx] = {
            "grounded": bool(r.get("grounded", True)),
            "filer": (str(r.get("filer")).strip() if r.get("filer") else None),
            "evidence": (str(r.get("evidence")).strip() if r.get("evidence") else None),
        }
        for p in r.get("picks") or []:
            if not isinstance(p, dict):
                continue
            t = str(p.get("ticker") or "").strip().upper()
            v = str(p.get("verdict") or "keep").strip().lower()
            if t and v in ("keep", "flag", "drop"):
                verdicts[(idx, t)] = {
                    "verdict": v,
                    "reason": str(p.get("reason") or "").strip(),
                    "is_filer": bool(p.get("is_filer", False)),
                }
    return grounding, verdicts


# ── 통합 적용 ─────────────────────────────────────────────────────
def apply_verification(
    issues: list[dict],
    *,
    scope: str,
    conn=None,
    evidence_lines: list[str] | None = None,
    fmp_api_key: str = "",
) -> list[dict]:
    """issues 의 picks 를 검증해 환각 제거 + verifyStatus 스탬프.

    - 촉매 grounded=false (날조 촉매) → 이슈째 제거
    - pick 'drop' → 해당 pick 제거 (종목↔촉매 연결 날조)
    - pick 'flag' (수혜주 근거 약함·오귀속 의심) → verifyStatus='review'
    - 티커 형식 오류(malformed) → verifyStatus='review'
    - 그 외 → verifyStatus='ok' (실존 미확인이어도 정상 종목 오탐 방지)
    실존 양성 확인은 신뢰도 보강용으로만 수행(플래그 근거로 쓰지 않음).
    LLM 판정이 비면(fail-open) 모두 keep — 파이프라인을 멈추지 않는다.
    """
    grounding, verdicts = verify_issues_llm(issues, evidence_lines or [])

    dropped = 0
    flagged = 0
    dropped_issues = 0
    kept_issues: list[dict] = []
    for idx, iss in enumerate(issues):
        # 1) 촉매 그라운딩 — 날조 촉매면 이슈 전체를 버린다.
        #    판정이 없으면(fail-open) grounded 로 취급해 정상 이슈를 잃지 않는다.
        g = grounding.get(idx, {})
        if g.get("grounded", True) is False:
            dropped_issues += 1
            dropped += len(iss.get("picks") or [])
            log.info(
                "pick_verify(%s): 이슈 제거(촉매 미확인) asset=%s signal=%s",
                scope,
                iss.get("asset", ""),
                iss.get("signal", ""),
            )
            continue

        # 2) 픽 단위 판정
        kept: list[dict] = []
        for p in iss.get("picks") or []:
            ticker = str(p.get("ticker") or "").strip().upper()
            v = verdicts.get((idx, ticker), {})
            verdict = v.get("verdict", "keep")
            if verdict == "drop":
                dropped += 1
                continue
            malformed = verify_ticker_format(ticker, scope) == "malformed"
            if verdict == "flag" or malformed:
                p["verifyStatus"] = "review"
                # 사유를 함께 저장해 '왜 추가 확인인지'를 UI 에 보여준다
                note = v.get("reason", "")
                if malformed and not note:
                    note = "티커 형식을 확인해 주세요"
                p["verifyNote"] = note
                flagged += 1
            else:
                p["verifyStatus"] = "ok"
            # 공시 주체 여부를 스탬프(UI·후속 분석용)
            if v:
                p["isFiler"] = bool(v.get("is_filer", False))
            # 실존 양성 확인(보강용) — 실패해도 플래그하지 않음
            if not malformed:
                p["tickerConfirmed"] = confirm_ticker_exists(ticker, scope, conn, fmp_api_key)
            kept.append(p)
        iss["picks"] = kept
        kept_issues.append(iss)

    log.info(
        "pick_verify(%s): 이슈제거 %d, pick drop %d, review %d",
        scope,
        dropped_issues,
        dropped,
        flagged,
    )
    return kept_issues
