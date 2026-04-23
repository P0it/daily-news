"""시사 뉴스 큐레이션 점수 (PRD F31).

공식: source_trust × recency × importance → 0~100 스케일.
- source_trust: 소스별 고정 신뢰도 (수동 튜닝)
- recency: 최근 6h=1.0, 12h=0.5, 24h=0.2, 48h+=0 (선형 근사)
- importance: LLM 판정 (0~1) 또는 기본 1.0. Week 3 고정, Week 4+ 에서 LLM 연결.
"""
from __future__ import annotations

from datetime import datetime

# 소스 신뢰도 (수동 튜닝)
SOURCE_TRUST: dict[str, float] = {
    # 연합뉴스: 통신사, 사실 전달 위주 → 높음
    "rss:yonhap-politics": 0.85,
    "rss:yonhap-society": 0.85,
    "rss:yonhap-intl": 0.85,
    # 일간지: 오피니언 색 있음 → 중간
    "rss:hani-politics": 0.75,
    "rss:hani-society": 0.75,
    # 해외 공신력 큰 곳
    "rss:bbc-world": 0.9,
    "rss:bbc-business": 0.9,
    "rss:reuters-world": 0.9,
    # IT/과학 전문지
    "rss:zdnet-kr": 0.7,
    "rss:etnews": 0.7,
    # 경제지
    "rss:hankyung": 0.8,
    "rss:mk": 0.8,
    "rss:ft-markets": 0.85,
}

DEFAULT_TRUST = 0.5


def recency_factor(published_at: datetime, now: datetime) -> float:
    """최근성 점수 (0~1).

    6h 이내 = 1.0, 12h = 0.5, 24h = 0.2, 48h+ = 0.0 (선형).
    미래 시각은 1.0 (시계 오차 케이스).
    """
    delta = now - published_at
    if delta.total_seconds() < 0:
        return 1.0
    hours = delta.total_seconds() / 3600
    if hours <= 6:
        return 1.0
    if hours <= 12:
        return 1.0 - (hours - 6) * (0.5 / 6)  # 6~12h → 1.0 to 0.5
    if hours <= 24:
        return 0.5 - (hours - 12) * (0.3 / 12)  # 12~24h → 0.5 to 0.2
    if hours <= 48:
        return max(0.0, 0.2 - (hours - 24) * (0.2 / 24))  # 24~48h → 0.2 to 0.0
    return 0.0


def curation_score(
    *,
    source: str,
    published_at: datetime,
    now: datetime,
    importance: float = 1.0,
) -> int:
    trust = SOURCE_TRUST.get(source, DEFAULT_TRUST)
    rec = recency_factor(published_at, now)
    imp = max(0.0, min(1.0, importance))
    score = round(trust * rec * imp * 100)
    return max(0, min(100, score))
