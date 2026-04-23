"""테마 키워드 등장 빈도 기반 트렌드 감지 (ROADMAP Week 3 작업 항목 8)."""
from __future__ import annotations

from datetime import datetime, timedelta

SPIKE_THRESHOLD = 2.0   # 오늘 빈도 / 주간 일평균이 이 값 이상이면 spike
MIN_TODAY_COUNT = 3     # 오늘 최소 등장 횟수 (노이즈 방지)


def _matches(title: str, keywords: list[str]) -> bool:
    return any(k in title for k in keywords)


def detect_trending_themes(
    events: list[tuple[str, datetime]],
    *,
    theme_keywords: dict[str, list[str]],
    now: datetime,
    lookback_days: int = 7,
) -> list[str]:
    """이동평균 대비 spike 가 발생한 theme_id 리스트 반환.

    - 오늘 MIN_TODAY_COUNT 이상 등장 필요
    - 과거 없는 신규 테마면 즉시 trending
    - 과거 있으면 (오늘 횟수) / (일평균) ≥ SPIKE_THRESHOLD 인지 체크
    """
    today_start = datetime(now.year, now.month, now.day)
    lookback_start = today_start - timedelta(days=lookback_days)

    trending: list[str] = []
    for theme_id, kws in theme_keywords.items():
        today_count = sum(
            1 for title, ts in events
            if ts >= today_start and _matches(title, kws)
        )
        past_count = sum(
            1 for title, ts in events
            if lookback_start <= ts < today_start and _matches(title, kws)
        )
        if today_count < MIN_TODAY_COUNT:
            continue
        if past_count == 0:
            # 새로 등장한 테마
            trending.append(theme_id)
            continue
        daily_avg = past_count / lookback_days
        ratio = today_count / daily_avg
        if ratio >= SPIKE_THRESHOLD:
            trending.append(theme_id)
    return trending
