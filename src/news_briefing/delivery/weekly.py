"""주간 리포트 생성 (ROADMAP Week 3 기본 + Week 4 LLM 에세이 확장).

Week 3: 7일 브리핑 JSON 을 합쳐 상위 시그널 나열 HTML.
Week 4: LLM 에세이 + 트렌드 테마 배너 + 카톡 링크.
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WeeklyReport:
    week_id: str         # 'YYYY-Www' (ISO week)
    start_date: str      # YYYY-MM-DD
    end_date: str
    top_signals: list[dict]
    trending_themes: list[str]


def _iso_week(date: datetime) -> str:
    y, w, _ = date.isocalendar()
    return f"{y}-W{w:02d}"


def collect_weekly(
    briefings_dir: Path, *, now: datetime | None = None
) -> WeeklyReport:
    """지난 7일 브리핑 JSON 을 합쳐 상위 시그널 20개 추출."""
    now = now or datetime.now()
    end = now
    start = end - timedelta(days=6)

    all_signals: list[dict] = []
    for i in range(7):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        path = briefings_dir / f"{day}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("hero"):
            all_signals.append(data["hero"])
        all_signals.extend(
            data.get("tabs", {}).get("economy", {}).get("signals", [])
        )

    # id 기준 중복 제거
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for s in all_signals:
        sid = s.get("id")
        if sid and sid not in seen_ids:
            unique.append(s)
            seen_ids.add(sid)
    # 점수 내림차순 상위 20
    unique.sort(key=lambda s: s.get("score", 0), reverse=True)

    return WeeklyReport(
        week_id=_iso_week(end),
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        top_signals=unique[:20],
        trending_themes=[],  # Week 4 에서 trends.detect_trending_themes 연결
    )


def render_weekly_html(report: WeeklyReport) -> str:
    rows: list[str] = []
    for s in report.top_signals:
        company = html.escape(s.get("company") or "—")
        headline = html.escape(s.get("headline") or "")
        score = s.get("score", 0)
        url = html.escape(s.get("url") or "#")
        rows.append(
            f'  <li><strong>{company}</strong>: {headline} '
            f'(점수 {score}) <a href="{url}">원문</a></li>'
        )
    body = "\n".join(rows) if rows else "  <li>이번 주 기록된 시그널이 없어요.</li>"
    return (
        "<!doctype html>\n"
        '<html lang="ko"><head><meta charset="utf-8">'
        f"<title>주간 리포트 · {html.escape(report.week_id)}</title>"
        '<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6}</style>'
        "</head><body>"
        f"<h1>주간 리포트 · {html.escape(report.week_id)}</h1>"
        f"<p>{html.escape(report.start_date)} ~ {html.escape(report.end_date)}</p>"
        f"<h2>주요 시그널 상위 {len(report.top_signals)}건</h2>"
        f"<ol>\n{body}\n</ol>"
        "</body></html>\n"
    )


def write_weekly(*, reports_dir: Path, report: WeeklyReport) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{report.week_id}.html"
    path.write_text(render_weekly_html(report), encoding="utf-8")
    return path
