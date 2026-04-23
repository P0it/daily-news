from __future__ import annotations

from datetime import datetime, timedelta

from news_briefing.analysis.trends import detect_trending_themes


def test_no_spike_no_trending() -> None:
    now = datetime(2026, 4, 23)
    events = [(f"로봇 기사 {i}", now - timedelta(days=i)) for i in range(7)]
    trending = detect_trending_themes(
        events, theme_keywords={"robotics": ["로봇"]}, now=now
    )
    assert trending == []


def test_spike_detected() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    # 오늘 5건
    today = [(f"로봇 붐 {i}", now.replace(hour=i)) for i in range(5)]
    # 지난 7일 매일 1건
    past = [(f"로봇 평상시 {i}", now - timedelta(days=i + 1)) for i in range(7)]
    trending = detect_trending_themes(
        today + past,
        theme_keywords={"robotics": ["로봇"]},
        now=now,
    )
    assert "robotics" in trending


def test_multiple_keywords_match_any() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    today = [(f"HBM 발표 {i}", now.replace(hour=i)) for i in range(4)]
    past = [(f"평상시 {i}", now - timedelta(days=i + 1)) for i in range(7)]
    trending = detect_trending_themes(
        today + past,
        theme_keywords={"ai_semi": ["HBM", "AI 반도체", "파운드리"]},
        now=now,
    )
    assert "ai_semi" in trending


def test_new_theme_no_past_data_trending() -> None:
    """과거 데이터 없는데 오늘 최소 임계값 이상이면 신규 주목 테마."""
    now = datetime(2026, 4, 23, 12, 0)
    today = [(f"신규테마 {i}", now.replace(hour=i)) for i in range(4)]
    trending = detect_trending_themes(
        today, theme_keywords={"new_theme": ["신규테마"]}, now=now
    )
    assert "new_theme" in trending


def test_below_min_today_count_not_trending() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    today = [("로봇", now)]  # 1건만
    trending = detect_trending_themes(
        today, theme_keywords={"robotics": ["로봇"]}, now=now
    )
    assert trending == []
