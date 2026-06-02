"""밸류체인 LLM 분해 + 기업 포지셔닝 생성 (SIGNALS.md 4절).

호출 비용 큼 — 자동 배치 아님. 수동 CLI (`themes refresh <theme_id>`) 전용.
"""
from __future__ import annotations

import json
import logging
import sqlite3

from news_briefing.analysis.llm import _call_claude
from news_briefing.storage.themes import (
    Theme,
    ValueLayer,
    upsert_layer,
)

log = logging.getLogger(__name__)


DECOMPOSE_PROMPT = (
    "당신은 투자 기회를 발굴하는 산업 애널리스트다. 다음 테마의 밸류체인을 "
    "3~5개 레이어로 분해하되, **아직 시장에서 주목받지 못한 2차·3차 수혜 기업**을 "
    "발굴하는 것이 최우선 목표다.\n\n"
    "테마: {theme_name}\n\n"
    "출력은 JSON 한 덩어리로. 형식:\n"
    "{{\n"
    '  "layers": [\n'
    '    {{\n'
    '      "name": "레이어명",\n'
    '      "description": "이 레이어가 무엇이고 왜 이 테마의 핵심 부품/서비스인지",\n'
    '      "order": 1,\n'
    '      "discovery_difficulty": "1차(명백)/2차(추론필요)/3차(비연속적 연결)"\n'
    '    }},\n'
    "    ...\n"
    "  ],\n"
    '  "hidden_beneficiaries": [\n'
    '    {{\n'
    '      "company": "기업명",\n'
    '      "reason": "왜 아직 주목받지 못했는지 — 애널리스트 커버리지 부족·소형주·간접 수혜 등",\n'
    '      "connection": "이 테마와 어떻게 연결되는지 2문장",\n'
    '      "risk": "연결 논리가 틀릴 수 있는 이유"\n'
    '    }}\n'
    "  ],\n"
    '  "caveats": "밸류체인 분해 시 유의사항 1~2줄"\n'
    "}}\n\n"
    "규칙:\n"
    "- 1차 수혜(이미 언론에 자주 언급된 대장주)는 hidden_beneficiaries에서 제외\n"
    "- hidden_beneficiaries는 시총 1조 이하 · 애널리스트 커버리지 3건 이하 기업 우선\n"
    "- '관련 있음' 수준의 먼 연결도 포함하되 risk 필드에 불확실성을 명시\n"
    "- 검증 안 된 연결은 '추가 확인 필요' 플래그\n"
    "- 존댓말 '~요' 체 사용"
)


POSITIONING_PROMPT = (
    "당신은 기업 리서처다. 다음 기업이 '{layer}' 레이어에서 "
    "어떤 포지션을 갖는지 한국어 1~2 문장으로 정리해줘.\n\n"
    "기업: {company_name} (티커 {ticker})\n"
    "레이어: {layer}\n\n"
    "추가로 다음도 한 문장씩 답해줘:\n"
    "1) 이 기업이 아직 시장에서 저평가·미발굴된 이유가 있다면 무엇인지\n"
    "2) 이 테마 모멘텀이 가속될 때 가장 먼저 주가에 반영될 촉매(catalyst)는 무엇인지\n\n"
    "규칙:\n"
    "- 사실 기반 (숫자는 공개 정보 기준)\n"
    "- '매수 유망', '추천' 등 투자 유인 표현 절대 금지\n"
    "- 공개 정보 부족 시 '공개 정보 부족' 으로 명시\n"
    "- 존댓말 '~요' 체 (총 4문장 이내)"
)


def decompose_theme(theme_name: str) -> dict | None:
    """테마 → layers LLM 분해. 실패 시 None."""
    try:
        raw = _call_claude(DECOMPOSE_PROMPT.format(theme_name=theme_name), timeout=60)
    except Exception as e:
        log.error("theme decompose 실패 %s: %s", theme_name, e)
        return None
    text = raw.strip()
    # Claude 가 코드블록으로 감쌀 수 있음
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3]
    try:
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


def refresh_theme_layers(conn: sqlite3.Connection, theme: Theme) -> int:
    """테마의 밸류체인 레이어를 LLM 으로 재생성. 반환: 갱신된 layer 개수."""
    result = decompose_theme(theme.name_ko)
    if result is None:
        return 0
    n = 0
    for layer_data in result.get("layers", []):
        upsert_layer(
            conn,
            ValueLayer(
                layer_id=None,
                theme_id=theme.theme_id,
                name=layer_data["name"],
                description=layer_data.get("description"),
            ),
        )
        n += 1
    return n
