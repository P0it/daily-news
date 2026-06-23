"""낙수효과 수혜주 분석 — 관찰 리스트 보조 레이어.

관찰(watchlist)에 오른 강한 이벤트(횡령·감자·영업정지·리콜·합병 등)가
경쟁사·대체재·공급망에 만드는 반사이익(낙수효과) 수혜주를 추론한다.

이건 본질적으로 2·3차 파생 추론이라 정식 픽(strict·검증·알파 원장)과는
분리한다 — 관찰 항목에 저컨빅션 'beneficiaries' 로만 붙이고, 성과 채점에는
넣지 않는다. 연결고리가 약하면 빈 배열을 돌려 머릿수를 채우지 않는다.

LLM 1회 배치 호출(Claude Code CLI, Max 플랜). 실패하면 빈 결과로 fail-open.
"""

from __future__ import annotations

import json
import logging
import re

log = logging.getLogger(__name__)

_PROMPT = """\
너는 이벤트 드리븐 리서치 애널리스트다. 아래는 오늘의 주요 공시 '관찰 목록'이다.
각 항목의 사건이 **다른 기업**에 만드는 낙수효과(경쟁사·대체재·공급망 반사이익)
수혜주를 분석하라.

규칙:
- 사건 당사자(공시 주체) 본인은 수혜주가 아니다. 그 사건으로 반사이익을 보는 **별도 기업**만.
  예: A사 횡령·생산차질 → 동일 제품 경쟁사 B. A사 감자·유동성위기 → 점유율 흡수하는 C.
- 연결고리가 명확할 때만 제시한다. 약하거나 억지스러우면 beneficiaries=[] (빈 배열).
  머릿수를 채우지 마라 — 추론 수혜주는 손실이 가장 많이 나는 패턴이다.
- 항목당 수혜주 1~2개. 각자 수혜 메커니즘 1문장.
- confidence 는 "low" 또는 "medium" 만 (본질이 추론이므로 high 금지).
- ticker: {ticker_rule}

출력 규칙:
- JSON 객체만 반환. 마크다운·설명 없이.
- 형식: {{"items":[{{"idx":0,"beneficiaries":[{{"name":"기업명","ticker":"코드",
  "reason":"수혜 메커니즘 한 문장","confidence":"low|medium"}}]}}]}}
- 입력의 모든 idx 를 빠짐없이 포함한다. 수혜주가 없으면 beneficiaries=[].
"""

_TICKER_RULE = {
    "domestic": "한국 종목코드 6자리 숫자 (예: 005930).",
    "foreign": "미국 거래소 티커 (예: NVDA).",
}


def _items_to_block(items: list[dict]) -> str:
    """관찰 항목을 idx·회사·사건 단위로 직렬화."""
    lines: list[str] = []
    for idx, w in enumerate(items):
        company = w.get("company", "")
        title = w.get("title", "")
        direction = w.get("direction", "")
        lines.append(f"[{idx}] 회사={company} | 사건={title} | 방향={direction}")
    return "\n".join(lines)


def _parse_spillover(raw: str, n_items: int) -> dict[int, list[dict]]:
    """LLM 출력 → {idx: [beneficiary, ...]}. 검증·정규화 포함.

    파싱 실패·형식 오류 시 빈 dict (fail-open). idx 범위 밖은 버린다.
    """
    raw = raw.strip()
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
            return {}
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}

    out: dict[int, list[dict]] = {}
    rows = obj.get("items", []) if isinstance(obj, dict) else []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        try:
            idx = int(r.get("idx"))
        except (TypeError, ValueError):
            continue
        if not 0 <= idx < n_items:
            continue
        bens: list[dict] = []
        for b in r.get("beneficiaries") or []:
            if not isinstance(b, dict):
                continue
            name = str(b.get("name") or "").strip()
            if not name:
                continue
            conf = str(b.get("confidence") or "low").strip().lower()
            bens.append(
                {
                    "name": name,
                    "code": str(b.get("ticker") or "").strip() or None,
                    "reason": str(b.get("reason") or "").strip(),
                    "confidence": conf if conf in ("low", "medium") else "low",
                }
            )
        if bens:
            out[idx] = bens
    return out


def analyze_spillover(items: list[dict], *, scope: str) -> list[dict]:
    """관찰 항목에 낙수효과 수혜주(beneficiaries)를 붙여 반환.

    원본 items 를 변형하지 않고 새 리스트를 돌려준다. LLM 실패 시 입력 그대로.
    """
    if not items:
        return items

    from news_briefing.analysis.llm import _call_claude  # noqa: PLC0415

    ticker_rule = _TICKER_RULE.get(scope, _TICKER_RULE["foreign"])
    prompt = _PROMPT.format(ticker_rule=ticker_rule) + "\n\n## 관찰 목록\n" + _items_to_block(items)

    try:
        raw = _call_claude(prompt, timeout=120, model="sonnet")
        mapping = _parse_spillover(raw, len(items))
    except Exception as e:
        log.warning("spillover(%s) 분석 실패 (수혜주 없이 진행): %s", scope, e)
        return items

    enriched = [dict(w) for w in items]
    total = 0
    for idx, bens in mapping.items():
        enriched[idx]["beneficiaries"] = bens
        total += len(bens)
    log.info("spillover(%s): %d개 항목에 수혜주 %d개", scope, len(mapping), total)
    return enriched
