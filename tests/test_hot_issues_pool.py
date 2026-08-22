"""hot_issues 후보 풀 구성 단위 테스트 — 네트워크·LLM 의존 없음.

국내 후보 굶주림 회귀 방지가 목적이다. 하한을 전 티어에 공통 적용하면
소스 신뢰도로 점수를 매긴 뉴스(42~65)가 촉매 하한(75)에 전멸해
LLM 이 후보 2건으로 Top 3 를 뽑아야 하는 상황이 된다.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from news_briefing.analysis.hot_issues import (
    _build_pool,
    domestic_news_weight,
    foreign_news_weight,
    source_tier_domestic,
)
from news_briefing.collectors.base import CollectedItem

_NOW = datetime.now(timezone.utc)

DOMESTIC_CAPS = {"tier1_cap": 20, "tier2_cap": 12, "tier3_cap": 3}


def _item(source: str, title: str, company: str, kind: str = "news") -> CollectedItem:
    return CollectedItem(
        source=source,
        ext_id=f"{source}:{title}",
        kind=kind,
        title=title,
        url="https://example.test",
        published_at=_NOW,
        company=company,
    )


def _domestic_candidates() -> list[tuple[CollectedItem, int]]:
    """실제 아침 구성 재현 — DART 소수 + 국내 뉴스 다수."""
    cands: list[tuple[CollectedItem, int]] = [
        (_item("dart", "주요사항보고서(전환사채권발행결정)", "엔투텍", "disclosure"), 85),
        (_item("dart", "단일판매·공급계약체결", "A사", "disclosure"), 75),
        (_item("dart", "분기보고서", "B사", "disclosure"), 45),
    ]
    for i in range(6):
        cands.append((_item("rss:hankyung", f"한경{i}", f"한경사{i}"), domestic_news_weight("rss:hankyung")))
    for i in range(5):
        cands.append((_item("rss:mk", f"매경{i}", f"매경사{i}"), domestic_news_weight("rss:mk")))
    for i in range(4):
        cands.append(
            (_item("rss:gnews-stock-kr", f"구글{i}", f"구글사{i}"), domestic_news_weight("rss:gnews-stock-kr"))
        )
    return cands


def _tier_counts(pool: list[tuple[CollectedItem, int, int]]) -> Counter:
    return Counter(tier for *_, tier in pool)


def test_domestic_news_weight_matches_tier() -> None:
    """국내 뉴스 가중치는 소스 티어를 따른다 (foreign_news_weight 와 대칭)."""
    assert domestic_news_weight("rss:hankyung") == 50  # Tier 2
    assert domestic_news_weight("rss:mk") == 50
    assert domestic_news_weight("rss:yonhap-kr") == 50
    assert domestic_news_weight("rss:gnews-stock-kr") == 42  # Tier 3
    assert domestic_news_weight("듣도보도못한소스") == 42  # 미등록 → Tier 3 취급


def test_domestic_news_weight_clears_tier23_floor() -> None:
    """모든 국내 뉴스 가중치가 tier23_floor(40) 위에 있어야 한다.

    하나라도 40 미만이면 해당 소스가 조용히 전멸한다.
    """
    for source in ("rss:hankyung", "rss:mk", "rss:yonhap-kr", "rss:gnews-stock-kr"):
        assert domestic_news_weight(source) >= 40


def test_common_floor_starves_domestic_news() -> None:
    """회귀 재현: 하한을 공통 적용하면 Tier2·3 이 전멸한다."""
    pool = _build_pool(
        _domestic_candidates(),
        source_tier_domestic,
        tier1_floor=75,
        tier23_floor=75,  # 수정 전 동작
        **DOMESTIC_CAPS,
    )
    counts = _tier_counts(pool)
    assert counts[2] == 0
    assert counts[3] == 0
    assert len(pool) == 2  # DART 고득점 2건뿐 — LLM 이 Top 3 를 뽑을 수 없다


def test_split_floor_admits_domestic_news() -> None:
    """티어별 하한 분리 후 뉴스가 후보 풀에 진입한다."""
    pool = _build_pool(
        _domestic_candidates(),
        source_tier_domestic,
        tier1_floor=75,
        tier23_floor=40,
        **DOMESTIC_CAPS,
    )
    counts = _tier_counts(pool)
    assert counts[2] > 0, "한경·매경이 후보에 없다"
    assert counts[3] > 0, "구글뉴스가 후보에 없다"
    assert len(pool) >= 10


def test_tier1_floor_still_blocks_non_catalyst_filings() -> None:
    """Tier2·3 을 열어도 비촉매 정기 공시는 계속 걸러져야 한다.

    분기보고서(45)·반기보고서(50)가 들어오면 제출 시즌에 실제 촉매를 밀어낸다.
    """
    pool = _build_pool(
        _domestic_candidates(),
        source_tier_domestic,
        tier1_floor=75,
        tier23_floor=40,
        **DOMESTIC_CAPS,
    )
    titles = [item.title for item, *_ in pool]
    assert "분기보고서" not in titles
    assert "단일판매·공급계약체결" in titles


def test_default_floors_leave_foreign_path_unchanged() -> None:
    """기본값은 40/40 — 해외 경로는 기존 동작(공통 하한 40)을 유지한다."""
    cands = [
        (_item("rss:ft-markets", "FT 기사", "FT사"), foreign_news_weight("rss:ft-markets")),
        (_item("rss:marketwatch", "MW 기사", "MW사"), foreign_news_weight("rss:marketwatch")),
        (_item("rss:unknown-en", "기타 기사", "기타사"), foreign_news_weight("rss:unknown-en")),
        (_item("dart", "저득점 항목", "탈락사", "disclosure"), 39),
    ]
    from news_briefing.analysis.hot_issues import source_tier_foreign

    pool = _build_pool(cands, source_tier_foreign, tier1_cap=10, tier2_cap=8, tier3_cap=3)
    titles = [item.title for item, *_ in pool]
    assert "저득점 항목" not in titles  # 40 미만은 제외
    assert len(pool) == 3
