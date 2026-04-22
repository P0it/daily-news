"""브리핑 텍스트 백업 생성 (`data/digests/YYYY-MM-DD.txt`)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem

ScoredSignal = tuple[CollectedItem, int, str]  # (item, score, direction)

DIRECTION_LABEL = {
    "positive": "긍정",
    "negative": "주의",
    "mixed": "복합",
    "neutral": "중립",
}


def format_digest(
    *,
    date: datetime,
    scored_signals: list[ScoredSignal],
    news: list[CollectedItem],
    min_score: int = 60,
) -> str:
    lines: list[str] = []
    lines.append(f"데일리 브리핑 · {date.strftime('%Y-%m-%d')}")
    lines.append("")

    filtered = [s for s in scored_signals if s[1] >= min_score]
    filtered.sort(key=lambda x: x[1], reverse=True)

    if filtered:
        lines.append(f"공시 {len(filtered)}건")
        lines.append("-" * 32)
        for item, score, direction in filtered:
            label = DIRECTION_LABEL.get(direction, direction)
            company = item.company or "(회사명 없음)"
            lines.append(f"[{score} {label}] {company} · {item.title}")
            if item.body:
                lines.append(f"  {item.body[:80]}")
            lines.append(f"  {item.url}")
            lines.append("")
    else:
        lines.append("오늘은 조용한 장이에요. 주목할 공시가 없어요.")
        lines.append("")

    if news:
        lines.append(f"뉴스 {len(news)}건")
        lines.append("-" * 32)
        for n in news[:10]:
            lines.append(f"· {n.title}")
            lines.append(f"  {n.url}")
        lines.append("")

    return "\n".join(lines)


def write_digest(*, digests_dir: Path, date: datetime, text: str) -> Path:
    digests_dir.mkdir(parents=True, exist_ok=True)
    path = digests_dir / f"{date.strftime('%Y-%m-%d')}.txt"
    path.write_text(text, encoding="utf-8")
    return path
