from __future__ import annotations

import pytest

from news_briefing.analysis.scoring import score_report


@pytest.mark.parametrize(
    "report_name, expected_score, expected_direction",
    [
        # SIGNALS.md 2.1 순서대로
        ("횡령ㆍ배임혐의 발생", 95, "negative"),
        ("감자결정", 90, "negative"),
        ("관리종목지정", 90, "negative"),
        ("최대주주변경", 85, "mixed"),
        ("영업(잠정)실적공시", 85, "mixed"),
        ("주요사항보고서(자기주식취득결정)", 85, "mixed"),  # 주요사항보고가 먼저 매칭
        ("자기주식취득결정", 80, "positive"),
        ("합병결정", 80, "mixed"),
        ("단일판매ㆍ공급계약체결", 75, "positive"),
        ("대규모기업집단현황공시", 75, "neutral"),
        ("유상증자결정", 75, "mixed"),
        ("자기주식처분결정", 70, "mixed"),
        ("임원ㆍ주요주주특정증권등소유상황보고서", 70, "mixed"),
        ("전환사채권발행결정", 70, "mixed"),
        ("무상증자결정", 60, "positive"),
        ("사업보고서", 55, "neutral"),
        ("반기보고서", 50, "neutral"),
        ("분기보고서", 45, "neutral"),
        ("알수없는유형", 30, "neutral"),
    ],
)
def test_score_report_matches_signals_table(
    report_name: str, expected_score: int, expected_direction: str
) -> None:
    score, direction = score_report(report_name)
    assert score == expected_score
    assert direction == expected_direction


def test_scoring_is_priority_ordered() -> None:
    """주요사항보고서(자기주식취득결정) 는 주요사항보고(85)로 매칭되어야 함.

    자기주식취득(80) 보다 우선순위가 높아서.
    """
    score, _ = score_report("주요사항보고서(자기주식취득결정)")
    assert score == 85
