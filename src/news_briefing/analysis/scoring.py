"""공시 유형별 기본 점수 산정 (SIGNALS.md 2.1 표 기반).

키워드 매칭은 순서대로 진행하며 먼저 걸리는 규칙의 가중치를 적용한다.
Week 2 에서는 정량 보정(금액·지분율)을 추가한다.
"""
from __future__ import annotations

from typing import Literal

Direction = Literal["positive", "negative", "mixed", "neutral"]

# SIGNALS.md 2.1 표 — 우선순위대로
SIGNAL_WEIGHTS: list[tuple[str, int, Direction]] = [
    ("횡령", 95, "negative"),
    ("배임", 95, "negative"),
    ("감자결정", 90, "negative"),
    ("관리종목지정", 90, "negative"),
    ("최대주주변경", 85, "mixed"),
    ("영업(잠정)실적", 85, "mixed"),
    ("주요사항보고", 85, "mixed"),
    ("자기주식취득", 80, "positive"),
    ("합병", 80, "mixed"),
    ("단일판매", 75, "positive"),
    ("공급계약", 75, "positive"),
    ("대규모기업집단", 75, "neutral"),
    ("유상증자", 75, "mixed"),
    ("자기주식처분", 70, "mixed"),
    ("임원ㆍ주요주주", 70, "mixed"),
    ("전환사채", 70, "mixed"),
    ("무상증자", 60, "positive"),
    ("사업보고서", 55, "neutral"),
    ("반기보고서", 50, "neutral"),
    ("분기보고서", 45, "neutral"),
]

DEFAULT_SCORE = 30
DEFAULT_DIRECTION: Direction = "neutral"


def score_report(report_name: str) -> tuple[int, Direction]:
    """공시 제목에서 우선순위 키워드를 매칭해 (점수, 방향성) 반환."""
    for keyword, score, direction in SIGNAL_WEIGHTS:
        if keyword in report_name:
            return score, direction
    return DEFAULT_SCORE, DEFAULT_DIRECTION
