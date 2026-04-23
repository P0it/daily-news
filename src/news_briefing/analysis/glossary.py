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
    # 증권 용어 (Week 2a)
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
    # 시사 용어 (Week 3, F32)
    "plenary_assembly": ("대법원 전원합의체", "전원합의체"),
    "floor_leader": ("원내대표", "원내대표"),
    "supplementary_budget": ("추경 (추가경정예산)", "추경"),
    "national_audit": ("국정감사", "국정감사"),
    "proportional_representation": ("연동형 비례대표제", "연동형 비례대표"),
    "constitutional_court": ("헌법재판소", "헌법재판소"),
    "prosecutor_investigation": ("검찰 수사", "검찰 수사"),
    # 거시 경제 용어 (Week 5a, F36)
    "base_rate": ("기준금리", "기준금리"),
    "interest_rate_cut": ("금리 인하", "금리 인하"),
    "interest_rate_hike": ("금리 인상", "금리 인상"),
    "cpi": ("소비자물가지수 (CPI)", "소비자물가"),
    "ppi": ("생산자물가지수 (PPI)", "생산자물가"),
    "gdp": ("국내총생산 (GDP)", "GDP"),
    "quantitative_easing": ("양적완화", "양적완화"),
    "fed_fomc": ("연준 FOMC", "FOMC"),
    "trade_balance": ("무역수지", "무역수지"),
    "exchange_rate": ("환율", "환율"),
    "foreign_reserves": ("외환보유액", "외환보유액"),
    "yield_curve": ("국채 금리 (일드커브)", "국채금리"),
    "inflation": ("인플레이션", "인플레이션"),
    "deflation": ("디플레이션", "디플레이션"),
    "recession": ("경기침체", "경기침체"),
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
    # 시사 용어
    "plenary_assembly": (
        "대법원 전원합의체",
        "대법원의 가장 높은 합의체예요. 전체 대법관 13명이 모여 "
        "법 해석의 방향을 정하는 결정을 해요. 하급심과 다른 판단을 내리기도 하고, "
        "이후 비슷한 사건의 기준이 돼요.",
        "neutral",
    ),
    "floor_leader": (
        "원내대표",
        "국회 안에서 각 정당의 '현장 지휘관' 역할이에요. 법안 협상, 본회의 일정, "
        "의원 표결 지도 등을 맡아요. 당 대표가 바깥 이미지라면, 원내대표는 "
        "실제 정치 실무를 움직여요.",
        "neutral",
    ),
    "supplementary_budget": (
        "추경 (추가경정예산)",
        "한 해 예산을 다 짜둔 뒤, 큰 변수(재난·경기 침체 등)가 생겨 "
        "추가로 편성하는 예산이에요. 규모·용도·재원 조달 방식이 핵심 쟁점이에요. "
        "국채 발행으로 조달하면 재정 건전성 논쟁이 따라와요.",
        "mixed",
    ),
    "national_audit": (
        "국정감사",
        "국회가 정부 기관의 일을 들여다보는 정기 감사예요. "
        "매년 9~10월 상임위원회별로 진행해요. 의원 질의가 크게 화제되는 시기라 "
        "특정 이슈가 정치적으로 증폭되곤 해요.",
        "neutral",
    ),
    "proportional_representation": (
        "연동형 비례대표제",
        "지역구 당선자 수와 정당 득표율을 연동해 전체 의석을 배분하는 방식이에요. "
        "득표에 못 미친 정당을 비례의석으로 보완해 민심 반영을 강화하려는 취지예요. "
        "위성정당 문제 등으로 실제 효과엔 논란이 있어요.",
        "neutral",
    ),
    "constitutional_court": (
        "헌법재판소",
        "법률이나 국가 행위가 헌법에 맞는지 판단하는 최고 재판소예요. "
        "위헌법률심판·헌법소원·탄핵심판 등을 다뤄요. "
        "대법원과 별개 기관이고, 헌법적 해석의 최종 권위예요.",
        "neutral",
    ),
    "prosecutor_investigation": (
        "검찰 수사",
        "범죄 혐의에 대해 검찰이 수사를 진행하는 단계예요. "
        "압수수색·소환조사·기소 여부 결정 순으로 이어져요. "
        "수사 개시 단계와 기소 단계는 법적 의미가 크게 달라요.",
        "neutral",
    ),
    # 거시 경제 (Week 5a, F36)
    "base_rate": (
        "기준금리",
        "한국은행이 시중 은행과 거래할 때 쓰는 기준이 되는 금리예요. "
        "이걸 올리면 대출·예금 금리가 줄줄이 오르고, 내리면 내려가요. "
        "물가·경기·환율을 조절하려는 목적으로 6주마다 금통위가 결정해요.",
        "mixed",
    ),
    "interest_rate_cut": (
        "금리 인하",
        "중앙은행이 기준금리를 낮추는 결정이에요. 대출 부담이 줄고 소비·투자 자극, "
        "성장 둔화·디플레이션 대응이 주 이유예요. 주식은 통상 긍정, "
        "예금자엔 불리예요.",
        "mixed",
    ),
    "interest_rate_hike": (
        "금리 인상",
        "중앙은행이 기준금리를 올리는 결정이에요. 인플레이션 억제가 주 목적이고 "
        "대출 이자가 오르고 소비·투자가 위축돼요. 주식엔 통상 부담, "
        "예금자엔 유리예요.",
        "mixed",
    ),
    "cpi": (
        "소비자물가지수 (CPI)",
        "소비자가 구입하는 상품·서비스 가격이 전년 대비 얼마나 변했는지 보여주는 지표예요. "
        "중앙은행이 금리를 움직일 때 가장 중요한 근거로 보는 수치예요. "
        "전년 동월 대비 2% 안팎이 일반적 목표예요.",
        "mixed",
    ),
    "ppi": (
        "생산자물가지수 (PPI)",
        "생산자가 출하하는 상품·서비스 가격 변화를 측정해요. "
        "소비자물가(CPI)보다 1~2달 선행하는 경향이 있어 물가 방향의 '선행지표' 로 봐요.",
        "mixed",
    ),
    "gdp": (
        "국내총생산 (GDP)",
        "한 나라가 일정 기간 동안 생산한 모든 재화·서비스의 가치 합이에요. "
        "전년 대비 성장률이 경제 활력의 대표 지표예요. "
        "분기마다 한국은행이 속보치→잠정치→확정치 순으로 발표해요.",
        "mixed",
    ),
    "quantitative_easing": (
        "양적완화 (QE)",
        "중앙은행이 시장에서 국채 등 자산을 대량 매입해 돈을 푸는 정책이에요. "
        "금리를 이미 0 근처로 내려도 경기가 안 살 때 쓰는 비전통적 수단이에요. "
        "자산 가격 상승 유발 → 주식·부동산에 통상 긍정이에요.",
        "positive",
    ),
    "fed_fomc": (
        "연준 FOMC (연방공개시장위원회)",
        "미국 중앙은행(Fed) 의 통화정책 결정 회의예요. 1년에 8번 열리고 "
        "연방기금금리(FFR) 조정·양적완화 등을 결정해요. "
        "한국 포함 전 세계 금융시장이 이 발표를 주시해요.",
        "mixed",
    ),
    "trade_balance": (
        "무역수지",
        "수출에서 수입을 뺀 값이에요. 플러스면 흑자(수출 > 수입), 마이너스면 적자예요. "
        "경상수지의 핵심 구성요소고, 환율·외환보유액·경제 성장에 큰 영향을 줘요.",
        "mixed",
    ),
    "exchange_rate": (
        "환율",
        "두 나라 통화 간 교환 비율이에요. 원·달러 환율 상승 = 원화 약세 = 수출에 유리·수입에 불리. "
        "미국 금리·무역수지·지정학 리스크 등 다양한 변수로 움직여요.",
        "mixed",
    ),
    "foreign_reserves": (
        "외환보유액",
        "한국은행이 가진 달러·유로·금 등 외환 자산의 총액이에요. "
        "외환위기에 대한 '안전판' 역할을 하고 환율 방어 수단이 돼요. "
        "매월 첫째 영업일에 발표돼요.",
        "neutral",
    ),
    "yield_curve": (
        "국채 금리 (일드커브)",
        "만기별 국채 금리를 연결한 곡선이에요. 단기 < 장기면 정상 커브, "
        "뒤집히면 '경기침체 신호' 로 유명해요. "
        "미국 10년물·2년물 격차가 대표 지표예요.",
        "mixed",
    ),
    "inflation": (
        "인플레이션",
        "물가가 지속적으로 오르는 현상이에요. 화폐 가치가 떨어지고 실질 구매력이 줄어요. "
        "대개 수요 증가·비용 증가·과잉 통화공급이 원인이에요. "
        "중앙은행이 금리로 억제하려 해요.",
        "negative",
    ),
    "deflation": (
        "디플레이션",
        "물가가 지속적으로 내려가는 현상이에요. 소비자가 '더 내려가겠지' 하고 소비를 미루면 "
        "경기 둔화가 악순환돼요. 중앙은행이 가장 경계하는 상황이에요.",
        "negative",
    ),
    "recession": (
        "경기침체",
        "실질 GDP 가 2분기 연속 마이너스 성장을 기록하는 상태를 보통 경기침체라고 해요. "
        "실업률 상승·소비 위축을 동반해요. 경기침체 판단은 각국 공식 기관이 사후에 선언해요.",
        "negative",
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
