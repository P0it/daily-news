"""ThesisCheck — 시그널별 리스크·선반영·타이밍 분석 에이전트.

75점 이상 시그널에 대해 쉬운 한국어로 3가지 질문에 답한다:
  1. 이 소식, 주가에 이미 반영됐나요?
  2. 어떤 위험이 있나요?
  3. 지금 들어가도 될까요?

캐시 지원. 실패 시 None 반환 — 파이프라인 중단 없음.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict, dataclass
from typing import Literal

from news_briefing.analysis.llm import _call_claude
from news_briefing.storage.cache import cache_get, cache_put

log = logging.getLogger(__name__)

THESIS_CHECK_TASK = "thesis_check"

_PROMPT_SYSTEM = """\
너는 개인 투자자의 친한 친구처럼 솔직하게 조언해주는 분석가다.
주어진 공시·리포트 내용을 보고 아래 3가지 질문에 답해라.

쉬운 말로 써라. 전문 금융 용어 사용 금지 (선반영, 밸류에이션, 컨센서스, 모멘텀, 어닝, 피봇 등).
어려운 개념은 비유나 쉬운 말로 풀어 설명해라.
자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓). 느낌표 금지. 매수·매도 권유 금지.

질문 1. 이 소식, 주가에 이미 반영됐나요?
  - 시장이 이 기대를 미리 알고 주가가 이미 많이 올라있다면 → "이미 반영됨"
  - 어느 정도 올랐지만 아직 여지가 있다면 → "어느 정도 반영됨"
  - 아직 시장이 주목하지 않아 주가에 반영 안 됐다면 → "아직 반영 안 됨"

질문 2. 어떤 위험이 있나요?
  이 좋은 소식에도 불구하고 주가가 내려갈 수 있는 이유 2~3가지를 쉬운 말로.
  좋은 예: "미국 정부가 예산을 줄이면 주문이 줄어들 수 있어요"
  나쁜 예: "단기 조정 리스크" (너무 모호함)

질문 3. 지금 들어가도 될까요?
  - "지금 가능": 현 시점이 크게 나쁘지 않아요
  - "좀 더 기다려요": 더 좋은 시점이 올 것 같아요
  - "조건 충족 시 진입": 특정 조건이 생기면 고려해볼 만해요

반드시 아래 JSON 형식으로만 답해라. 마크다운·설명·추가 텍스트 없이:
{
  "prepricing": "이미 반영됨" | "어느 정도 반영됨" | "아직 반영 안 됨",
  "prepricing_reason": "왜 그렇게 판단했는지 1문장, 쉬운 말",
  "risks": ["위험1", "위험2"],
  "macro_links": [
    {"factor": "예: 미국 금리", "impact": "금리가 오르면 이 분야에 불리한 이유 1문장"}
  ],
  "timing": "지금 가능" | "좀 더 기다려요" | "조건 충족 시 진입",
  "timing_condition": "어떤 조건이면 진입을 고려해볼 수 있는지 1문장"
}
"""

_VALID_PREPRICING = frozenset(["이미 반영됨", "어느 정도 반영됨", "아직 반영 안 됨"])
_VALID_TIMING = frozenset(["지금 가능", "좀 더 기다려요", "조건 충족 시 진입"])


@dataclass
class ThesisCheck:
    prepricing: Literal["이미 반영됨", "어느 정도 반영됨", "아직 반영 안 됨"]
    prepricing_reason: str
    risks: list[str]
    macro_links: list[dict]  # [{"factor": str, "impact": str}]
    timing: Literal["지금 가능", "좀 더 기다려요", "조건 충족 시 진입"]
    timing_condition: str

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_thesis(raw: str) -> ThesisCheck | None:
    """LLM JSON 출력 → ThesisCheck. 파싱 실패 시 None."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    try:
        data = json.loads(raw)
    except Exception:
        return None

    prepricing = str(data.get("prepricing", "")).strip()
    if prepricing not in _VALID_PREPRICING:
        prepricing = "어느 정도 반영됨"

    timing = str(data.get("timing", "")).strip()
    if timing not in _VALID_TIMING:
        timing = "좀 더 기다려요"

    risks_raw = data.get("risks") or []
    risks = [str(r).strip() for r in risks_raw if str(r).strip()][:3]

    macro_raw = data.get("macro_links") or []
    macro_links: list[dict] = []
    for m in macro_raw[:3]:
        if isinstance(m, dict) and m.get("factor"):
            macro_links.append({
                "factor": str(m.get("factor", "")).strip(),
                "impact": str(m.get("impact", "")).strip(),
            })

    return ThesisCheck(
        prepricing=prepricing,  # type: ignore[arg-type]
        prepricing_reason=str(data.get("prepricing_reason", "")).strip(),
        risks=risks,
        macro_links=macro_links,
        timing=timing,  # type: ignore[arg-type]
        timing_condition=str(data.get("timing_condition", "")).strip(),
    )


def analyze_thesis_batch(
    conn: sqlite3.Connection,
    signals: list[tuple[str, str, str, int]],  # (ext_id, company, headline, score)
    *,
    timeout: int = 60,
) -> dict[str, dict]:
    """점수 높은 시그널에 대한 ThesisCheck 분석.

    signals: [(ext_id, company, headline, score), ...]
    반환: {ext_id: ThesisCheck.to_dict()}  — 실패한 항목은 포함되지 않음.
    """
    result: dict[str, dict] = {}

    for ext_id, company, headline, score in signals:
        cache_key = f"{company}|{headline}"
        cached = cache_get(conn, THESIS_CHECK_TASK, cache_key)
        if cached is not None:
            try:
                result[ext_id] = json.loads(cached)
                continue
            except Exception:
                pass

        input_text = f"회사: {company}\n소식: {headline}\n중요도 점수: {score}점"
        prompt = f"{_PROMPT_SYSTEM}\n\n---\n\n{input_text}"

        try:
            raw = _call_claude(prompt, timeout=timeout)
            check = _parse_thesis(raw)
            if check:
                d = check.to_dict()
                cache_put(conn, THESIS_CHECK_TASK, cache_key, json.dumps(d, ensure_ascii=False), "claude-cli")
                result[ext_id] = d
                log.info("thesis_check 완료: %s (%s)", company, headline[:30])
            else:
                log.warning("thesis_check 파싱 실패: %s", headline[:50])
        except Exception as e:
            log.warning("thesis_check LLM 실패 (%s): %s", headline[:30], e)

    return result
