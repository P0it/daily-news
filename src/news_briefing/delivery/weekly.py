"""주간 리포트 생성 (Week 3 기본 + Week 4 LLM 에세이·트렌드)."""
from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from news_briefing.analysis.llm import _call_claude
from news_briefing.analysis.trends import detect_trending_themes

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WeeklyReport:
    week_id: str         # 'YYYY-Www' (ISO week)
    start_date: str
    end_date: str
    top_signals: list[dict]
    trending_themes: list[str]


ESSAY_PROMPT = (
    "당신은 금융·경제 브리핑 필자다. 아래 이번 주 상위 시그널·트렌드를 보고 "
    "500자 내외의 '이번 주 핵심 흐름' 에세이를 한국어로 써줘.\n\n"
    "상위 시그널:\n{signals}\n\n"
    "주목 테마: {themes}\n\n"
    "규칙:\n"
    "- 반말·느낌표 금지, 존댓말 '~요'\n"
    "- '매수 유망', '추천', '목표가' 같은 투자 유인 표현 금지\n"
    "- 흐름을 잡고 '섹터별·테마별' 관점에서 해석\n"
    "- 마지막 한 단락은 다음 주 관찰 포인트"
)


def _iso_week(date: datetime) -> str:
    y, w, _ = date.isocalendar()
    return f"{y}-W{w:02d}"


def collect_weekly(
    briefings_dir: Path,
    *,
    now: datetime | None = None,
    theme_keywords: dict[str, list[str]] | None = None,
) -> WeeklyReport:
    """지난 7일 브리핑 JSON 을 합쳐 상위 시그널 + 트렌드 테마 추출."""
    now = now or datetime.now()
    end = now
    start = end - timedelta(days=6)

    all_signals: list[dict] = []
    events: list[tuple[str, datetime]] = []

    for i in range(7):
        day_dt = start + timedelta(days=i)
        day = day_dt.strftime("%Y-%m-%d")
        path = briefings_dir / f"{day}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        hero = data.get("hero")
        if hero:
            all_signals.append(hero)
            events.append((hero.get("headline", ""), day_dt))
        economy = data.get("tabs", {}).get("economy", {})
        for s in economy.get("signals", []):
            all_signals.append(s)
            events.append((s.get("headline", ""), day_dt))
        for n in economy.get("news", []):
            events.append((n.get("title", ""), day_dt))

    # id 기준 중복 제거 + 점수 내림차순
    seen_ids: set[str] = set()
    unique: list[dict] = []
    for s in all_signals:
        sid = s.get("id")
        if sid and sid not in seen_ids:
            unique.append(s)
            seen_ids.add(sid)
    unique.sort(key=lambda s: s.get("score", 0), reverse=True)

    # 트렌드 테마 감지
    trending: list[str] = []
    if theme_keywords:
        trending = detect_trending_themes(
            events, theme_keywords=theme_keywords, now=end, lookback_days=7
        )

    return WeeklyReport(
        week_id=_iso_week(end),
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        top_signals=unique[:20],
        trending_themes=trending,
    )


def generate_essay(report: WeeklyReport) -> str | None:
    """LLM 으로 주간 에세이 생성. 실패 시 None."""
    if not report.top_signals:
        return None
    signals_text = "\n".join(
        f"- {s.get('company', '—')}: {s.get('headline', '')} "
        f"(점수 {s.get('score', 0)})"
        for s in report.top_signals[:10]
    )
    themes_text = (
        ", ".join(report.trending_themes) if report.trending_themes else "(없음)"
    )
    try:
        return _call_claude(
            ESSAY_PROMPT.format(signals=signals_text, themes=themes_text),
            timeout=60,
        ).strip()
    except Exception as e:
        log.warning("weekly essay LLM 실패: %s", e)
        return None


def render_weekly_html(report: WeeklyReport, essay: str | None = None) -> str:
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

    essay_section = ""
    if essay:
        paragraphs = "".join(
            f"<p>{html.escape(p)}</p>" for p in essay.split("\n\n") if p.strip()
        )
        essay_section = (
            '<section><h2>이번 주 핵심 흐름</h2>' f"{paragraphs}" "</section>"
        )

    themes_section = ""
    if report.trending_themes:
        themes_html = "".join(
            f"<li>{html.escape(t)}</li>" for t in report.trending_themes
        )
        themes_section = (
            '<section><h2>주목 테마</h2>' f"<ul>{themes_html}</ul>" "</section>"
        )

    return (
        "<!doctype html>\n"
        '<html lang="ko"><head><meta charset="utf-8">'
        f"<title>주간 리포트 · {html.escape(report.week_id)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:720px;"
        "margin:2rem auto;padding:0 1rem;line-height:1.6}</style>"
        "</head><body>"
        f"<h1>주간 리포트 · {html.escape(report.week_id)}</h1>"
        f"<p>{html.escape(report.start_date)} ~ {html.escape(report.end_date)}</p>"
        f"{essay_section}"
        f"{themes_section}"
        f"<h2>주요 시그널 상위 {len(report.top_signals)}건</h2>"
        f"<ol>\n{body}\n</ol>"
        "</body></html>\n"
    )


def write_weekly(
    *, reports_dir: Path, report: WeeklyReport, essay: str | None = None
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{report.week_id}.html"
    path.write_text(render_weekly_html(report, essay=essay), encoding="utf-8")
    return path
