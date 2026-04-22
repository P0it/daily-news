from __future__ import annotations

from datetime import datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem
from news_briefing.delivery.digest import format_digest, write_digest


def _item(title: str, score: int = 80, direction: str = "positive") -> tuple[CollectedItem, int, str]:
    it = CollectedItem(
        source="dart",
        ext_id="x",
        kind="disclosure",
        title=title,
        url="https://example.com",
        published_at=datetime(2026, 4, 22, 6, 0),
        company="테스트",
        company_code="000000",
    )
    return it, score, direction


def test_format_digest_includes_date_and_section_headers() -> None:
    scored = [_item("자기주식취득결정")]
    text = format_digest(date=datetime(2026, 4, 22), scored_signals=scored, news=[])
    assert "2026-04-22" in text
    assert "공시" in text


def test_format_digest_sorts_by_score_desc() -> None:
    scored = [
        _item("분기보고서", score=45, direction="neutral"),
        _item("횡령ㆍ배임", score=95, direction="negative"),
        _item("자기주식취득", score=80, direction="positive"),
    ]
    text = format_digest(date=datetime(2026, 4, 22), scored_signals=scored, news=[])
    h_idx = text.index("횡령")
    s_idx = text.index("자기주식")
    assert h_idx < s_idx


def test_format_digest_filters_below_threshold() -> None:
    scored = [
        _item("사업보고서", score=55, direction="neutral"),
        _item("분기보고서", score=45, direction="neutral"),
    ]
    text = format_digest(
        date=datetime(2026, 4, 22), scored_signals=scored, news=[], min_score=60
    )
    assert "사업보고서" not in text
    assert "분기보고서" not in text
    assert "조용한" in text or "없" in text  # 빈 상태 카피


def test_write_digest_creates_file(tmp_path: Path) -> None:
    written = write_digest(
        digests_dir=tmp_path,
        date=datetime(2026, 4, 22),
        text="안녕하세요",
    )
    assert written.exists()
    assert written.name == "2026-04-22.txt"
    assert written.read_text(encoding="utf-8") == "안녕하세요"
