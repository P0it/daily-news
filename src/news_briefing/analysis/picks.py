"""Today's Pick 선별 (DECISIONS #12).

시그널 점수 상위 N건, 같은 company_code 는 최고 점수만 남김,
국내(DART)/해외(EDGAR) 분리.
"""
from __future__ import annotations

from dataclasses import dataclass

from news_briefing.collectors.base import CollectedItem

ScoredSignal = tuple[CollectedItem, int, str]

DEFAULT_MIN_SCORE = 60


@dataclass(frozen=True, slots=True)
class PicksResult:
    domestic: list[ScoredSignal]
    foreign: list[ScoredSignal]


def _is_foreign(item: CollectedItem) -> bool:
    return item.source.startswith("edgar")


def _dedup_key(item: CollectedItem) -> tuple[str, str]:
    scope = "foreign" if _is_foreign(item) else "domestic"
    ident = item.company_code or item.company or item.ext_id
    return (scope, ident)


def select_picks(
    scored: list[ScoredSignal],
    *,
    n_per_side: int = 6,
    min_score: int = DEFAULT_MIN_SCORE,
) -> PicksResult:
    """국내/해외 상위 N. 같은 company_code 는 최고 점수만 남긴다.

    - min_score 미만은 제외
    - 각 side 별로 점수 내림차순 정렬 후 n_per_side 로 truncate
    """
    best_by_key: dict[tuple[str, str], ScoredSignal] = {}
    for item, score, direction in scored:
        if score < min_score:
            continue
        key = _dedup_key(item)
        existing = best_by_key.get(key)
        if existing is None or score > existing[1]:
            best_by_key[key] = (item, score, direction)

    domestic = [t for t in best_by_key.values() if not _is_foreign(t[0])]
    foreign = [t for t in best_by_key.values() if _is_foreign(t[0])]

    domestic.sort(key=lambda t: t[1], reverse=True)
    foreign.sort(key=lambda t: t[1], reverse=True)

    return PicksResult(
        domestic=domestic[:n_per_side],
        foreign=foreign[:n_per_side],
    )
