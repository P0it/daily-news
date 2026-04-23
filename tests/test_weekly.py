from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from news_briefing.delivery.weekly import (
    WeeklyReport,
    collect_weekly,
    render_weekly_html,
    write_weekly,
)


def _write_brief(dir: Path, date: str, signals: list[dict]) -> None:
    (dir / f"{date}.json").write_text(
        json.dumps(
            {
                "date": date,
                "generatedAt": "x",
                "version": 1,
                "hero": None,
                "tabs": {
                    "current": {},
                    "economy": {
                        "indices": [],
                        "signals": signals,
                        "news": [],
                    },
                    "picks": {"domestic": [], "foreign": []},
                },
                "glossary": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_collect_weekly_aggregates_last_7_days(tmp_path: Path) -> None:
    now = datetime(2026, 4, 23)
    for i in range(7):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        _write_brief(
            tmp_path,
            d,
            [
                {
                    "id": f"s{i}",
                    "company": "A",
                    "headline": "t",
                    "score": 60 + i,
                    "url": "x",
                }
            ],
        )
    report = collect_weekly(tmp_path, now=now)
    assert report.week_id.startswith("2026-W")
    assert len(report.top_signals) == 7
    # 내림차순
    scores = [s["score"] for s in report.top_signals]
    assert scores == sorted(scores, reverse=True)


def test_dedup_same_id_across_days(tmp_path: Path) -> None:
    _write_brief(
        tmp_path,
        "2026-04-22",
        [{"id": "dup", "company": "A", "headline": "t", "score": 70, "url": "x"}],
    )
    _write_brief(
        tmp_path,
        "2026-04-23",
        [{"id": "dup", "company": "A", "headline": "t", "score": 70, "url": "x"}],
    )
    report = collect_weekly(tmp_path, now=datetime(2026, 4, 23))
    assert len(report.top_signals) == 1


def test_collect_weekly_handles_missing_days(tmp_path: Path) -> None:
    # 7일 중 1개만 존재
    _write_brief(
        tmp_path,
        "2026-04-23",
        [{"id": "x", "company": "A", "headline": "t", "score": 80, "url": "u"}],
    )
    report = collect_weekly(tmp_path, now=datetime(2026, 4, 23))
    assert len(report.top_signals) == 1


def test_write_weekly_creates_html(tmp_path: Path) -> None:
    report = WeeklyReport(
        "2026-W17",
        "2026-04-19",
        "2026-04-25",
        top_signals=[
            {
                "company": "삼성전자",
                "headline": "자사주 매수",
                "score": 85,
                "url": "https://example.com",
            }
        ],
        trending_themes=[],
    )
    path = write_weekly(reports_dir=tmp_path, report=report)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "삼성전자" in content
    assert "85" in content


def test_render_empty_report_shows_placeholder() -> None:
    report = WeeklyReport("2026-W17", "2026-04-19", "2026-04-25", [], [])
    html_out = render_weekly_html(report)
    assert "시그널이 없어요" in html_out
