"""용어 해설 엔진.

공시 제목 → term_id 매핑 + seed 카탈로그 + LLM lazy 생성.
SIGNALS.md 3.2 예시를 seed 로 사용.
"""
from __future__ import annotations

import logging
import sqlite3

from news_briefing.analysis.llm import _call_claude
from news_briefing.storage.glossary import (
    GlossaryEntry,
    get_glossary_entry,
    upsert_glossary_entry,
)

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
    """공시 제목에서 term_id 를 추출. TERM_CATALOG 순서대로 매칭."""
    for term_id, (_label, keyword) in TERM_CATALOG.items():
        if keyword in report_name:
            return term_id
    return None


def _generate_explanation_via_llm(
    term_id: str, short_label_hint: str, lang: str
) -> tuple[str, str, str]:
    """LLM 으로 해설 생성. 실패 시 (short_label_hint, "", "neutral")."""
    prompt = (
        f"공시 용어 '{short_label_hint}' ({term_id}) 를 주식 초심자에게 "
        f"{lang} 로 설명해줘. "
        "형식: 1) 한 줄 별칭 (일상어) 2) 3~4줄 해설 3) 주의 한 줄. "
        "'사세요/파세요' 같은 권유 금지. '~요' 존댓말. "
        "첫 줄은 '라벨: ', 두 번째 단락은 '해설: ', 마지막은 "
        "'방향: positive|negative|mixed|neutral' 형식."
    )
    try:
        raw = _call_claude(prompt, timeout=45)
    except Exception as e:
        log.warning("glossary LLM 실패 %s: %s", term_id, e)
        return short_label_hint, "", "neutral"

    label = short_label_hint
    explanation = raw
    direction = "neutral"
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("라벨:"):
            label = line.split(":", 1)[1].strip()
        elif line.startswith("방향:"):
            direction = line.split(":", 1)[1].strip()
    if "해설:" in raw:
        explanation = raw.split("해설:", 1)[1].strip()

    if direction not in ("positive", "negative", "mixed", "neutral"):
        direction = "neutral"
    return label, explanation, direction


def ensure_glossary_entry(
    conn: sqlite3.Connection, term_id: str, lang: str = "ko"
) -> GlossaryEntry | None:
    """DB 에 있으면 반환, 없으면 seed 또는 LLM 으로 채운 뒤 반환."""
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
