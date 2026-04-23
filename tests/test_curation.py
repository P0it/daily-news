from __future__ import annotations

from datetime import datetime, timedelta

from news_briefing.analysis.curation import (
    SOURCE_TRUST,
    curation_score,
    recency_factor,
)


def test_source_trust_has_major_domestic_outlets() -> None:
    assert "rss:yonhap-politics" in SOURCE_TRUST
    assert "rss:hani-politics" in SOURCE_TRUST
    # 연합뉴스는 통신사 → 신뢰도 높음
    assert SOURCE_TRUST["rss:yonhap-politics"] >= 0.8


def test_recency_factor_decays_with_age() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    assert recency_factor(now - timedelta(hours=1), now) >= 0.9
    assert 0.4 <= recency_factor(now - timedelta(hours=12), now) <= 0.6
    assert recency_factor(now - timedelta(days=2), now) <= 0.1


def test_recency_factor_future_clamps_to_one() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    assert recency_factor(now + timedelta(hours=1), now) == 1.0


def test_curation_score_combines_factors() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    one_hour_ago = now - timedelta(hours=1)
    s = curation_score(
        source="rss:yonhap-politics",
        published_at=one_hour_ago,
        now=now,
        importance=0.8,
    )
    # 0.85 (trust) * ~1.0 (recency, 1h) * 0.8 (importance) * 100 ≈ 68
    assert 55 <= s <= 75


def test_curation_score_unknown_source_defaults_to_lower_trust() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    s = curation_score(
        source="rss:unknown-blog",
        published_at=now,
        now=now,
        importance=1.0,
    )
    # 0.5 (default trust) × 1.0 × 1.0 × 100 = 50
    assert 40 <= s <= 60


def test_curation_score_old_article_scores_low() -> None:
    now = datetime(2026, 4, 23, 12, 0)
    two_days_ago = now - timedelta(days=2)
    s = curation_score(
        source="rss:yonhap-politics",
        published_at=two_days_ago,
        now=now,
        importance=1.0,
    )
    # recency ≤ 0.1 이라 score ≤ 15
    assert s <= 15


def test_curation_score_clamps_0_to_100() -> None:
    now = datetime(2026, 4, 23)
    s_neg = curation_score(
        source="rss:unknown",
        published_at=now - timedelta(days=30),
        now=now,
        importance=-1.0,
    )
    assert 0 <= s_neg <= 100
