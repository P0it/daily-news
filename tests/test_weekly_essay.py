from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from news_briefing.delivery.weekly import (
    WeeklyReport,
    collect_weekly,
    generate_essay,
    render_weekly_html,
    write_weekly,
)


def test_generate_essay_calls_llm_with_signals(mocker) -> None:
    mocker.patch(
        "news_briefing.delivery.weekly._call_claude",
        return_value="이번 주는 반도체가 핵심이에요.",
    )
    r = WeeklyReport(
        "2026-W17",
        "2026-04-19",
        "2026-04-25",
        top_signals=[{"company": "삼성", "headline": "자사주", "score": 85}],
        trending_themes=["ai_semi"],
    )
    essay = generate_essay(r)
    assert essay == "이번 주는 반도체가 핵심이에요."


def test_generate_essay_empty_report_returns_none() -> None:
    r = WeeklyReport("x", "a", "b", [], [])
    assert generate_essay(r) is None


def test_generate_essay_llm_failure_returns_none(mocker) -> None:
    mocker.patch(
        "news_briefing.delivery.weekly._call_claude",
        side_effect=RuntimeError("LLM down"),
    )
    r = WeeklyReport(
        "x", "a", "b",
        top_signals=[{"company": "A", "headline": "h", "score": 70}],
        trending_themes=[],
    )
    assert generate_essay(r) is None


def test_render_includes_essay_when_provided() -> None:
    r = WeeklyReport(
        "2026-W17", "a", "b",
        top_signals=[
            {"company": "X", "headline": "Y", "score": 70, "url": "u"}
        ],
        trending_themes=["robotics"],
    )
    out = render_weekly_html(r, essay="첫 문단\n\n두 번째 문단")
    assert "핵심 흐름" in out
    assert "첫 문단" in out
    assert "두 번째 문단" in out
    assert "robotics" in out


def test_render_without_essay_has_no_essay_section() -> None:
    r = WeeklyReport(
        "2026-W17", "a", "b",
        top_signals=[{"company": "X", "headline": "Y", "score": 70, "url": "u"}],
        trending_themes=[],
    )
    out = render_weekly_html(r, essay=None)
    assert "핵심 흐름" not in out


def test_collect_weekly_extracts_trending_themes(tmp_path: Path) -> None:
    import json

    now = datetime(2026, 4, 23, 12, 0)
    # 오늘 '로봇' 많이
    today = now.strftime("%Y-%m-%d")
    today_data = {
        "date": today,
        "generatedAt": "x",
        "version": 1,
        "hero": None,
        "tabs": {
            "current": {},
            "economy": {
                "indices": [],
                "signals": [
                    {
                        "id": f"s{i}",
                        "headline": f"로봇 관련 공시 {i}",
                        "score": 70,
                    }
                    for i in range(4)
                ],
                "news": [],
            },
            "picks": {"domestic": [], "foreign": []},
        },
        "glossary": {},
    }
    (tmp_path / f"{today}.json").write_text(
        json.dumps(today_data, ensure_ascii=False), encoding="utf-8"
    )
    # 어제 평상시 1건
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    past_data = {
        "date": yesterday,
        "generatedAt": "x",
        "version": 1,
        "hero": None,
        "tabs": {
            "current": {},
            "economy": {
                "indices": [],
                "signals": [
                    {
                        "id": "old1",
                        "headline": "로봇 평상시",
                        "score": 60,
                    }
                ],
                "news": [],
            },
            "picks": {"domestic": [], "foreign": []},
        },
        "glossary": {},
    }
    (tmp_path / f"{yesterday}.json").write_text(
        json.dumps(past_data, ensure_ascii=False), encoding="utf-8"
    )

    report = collect_weekly(
        tmp_path,
        now=now,
        theme_keywords={"robotics": ["로봇"]},
    )
    assert "robotics" in report.trending_themes


def test_write_weekly_still_works_with_essay(tmp_path: Path) -> None:
    r = WeeklyReport(
        "2026-W17", "2026-04-19", "2026-04-25",
        top_signals=[
            {"company": "삼성", "headline": "자사주", "score": 85, "url": "u"}
        ],
        trending_themes=[],
    )
    path = write_weekly(reports_dir=tmp_path, report=r, essay="에세이 내용")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "에세이 내용" in content
    assert "삼성" in content
