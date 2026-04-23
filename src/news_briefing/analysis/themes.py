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
    "당신은 산업 애널리스트다. 다음 테마의 밸류체인을 "
    "3~5개 공통분모 레이어로 분해해줘.\n\n"
    "테마: {theme_name}\n\n"
    "출력은 JSON 한 덩어리로. 형식:\n"
    "{{\n"
    '  "layers": [\n'
    '    {{"name": "레이어명", "description": "이 레이어가 무엇이고 왜 이 테마의 핵심 부품/서비스인지"}},\n'
    "    ...\n"
    "  ],\n"
    '  "caveats": "밸류체인 분해 시 유의사항 1~2줄"\n'
    "}}\n\n"
    "규칙:\n"
    "- 완성품 제조사가 공유하는 부품/소재/플랫폼에 집중\n"
    "- '관련 있음' 수준의 먼 연결은 제외\n"
    "- 3~5개 레이어 이상 금지 (명료성 ↓)\n"
    "- 존댓말 '~요' 체 사용"
)


POSITIONING_PROMPT = (
    "당신은 기업 리서처다. 다음 기업이 '{layer}' 레이어에서 "
    "어떤 포지션을 갖는지 한국어 1~2 문장으로 정리해줘.\n\n"
    "기업: {company_name} (티커 {ticker})\n"
    "레이어: {layer}\n\n"
    "규칙:\n"
    "- 사실 기반 (숫자는 공개 정보 기준)\n"
    "- '매수 유망', '추천' 등 투자 유인 표현 절대 금지\n"
    "- 공개 정보 부족 시 '공개 정보 부족' 으로 명시\n"
    "- 존댓말 '~요' 체 (2문장 이내)"
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
